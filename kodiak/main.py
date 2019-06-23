from __future__ import annotations

import asyncio
import textwrap
import time
import typing
from dataclasses import dataclass, field
from enum import Enum, auto

import asyncio_redis
import sentry_sdk
import structlog
from asyncio_redis.connection import Connection as RedisConnection
from asyncio_redis.replies import BlockingZPopReply
from fastapi import FastAPI
from pydantic import BaseModel
from sentry_asgi import SentryMiddleware

import kodiak.app_config as conf
from kodiak import queries
from kodiak.config import V1, BodyText, MergeBodyStyle, MergeTitleStyle
from kodiak.evaluation import (
    BranchMerged,
    MergeConflict,
    MissingAppID,
    MissingGithubMergeabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
    mergeable,
)
from kodiak.github import Webhook, events
from kodiak.queries import Client, EventInfoResponse, PullRequest

sentry_sdk.init()

app = FastAPI()
app.add_middleware(SentryMiddleware)

webhook = Webhook(app)
logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"

WEBHOOK_QUEUE_NAME = "kodiak_webhooks"

WORKER_TASKS: typing.MutableMapping[str, asyncio.Task] = {}

MERGE_RETRY_RATE_SECONDS = 2


async def webhook_event_consumer(*, connection: RedisConnection) -> typing.NoReturn:
    """
    Worker to process incoming webhook events from redis

    1. process mergeability information and update github check status for pr
    2. enqueue pr into repo queue for merging, if mergeability passed
    """
    log = logger.bind(queue=WEBHOOK_QUEUE_NAME)
    log.info("start webhook event consumer")

    while True:
        log.info("block for new webhook event")
        webhook_event_json: BlockingZPopReply = await connection.bzpopmin(
            [WEBHOOK_QUEUE_NAME]
        )
        # process event in separate task to increase concurrency
        asyncio.create_task(
            pr_check_worker(
                webhook_event_json=webhook_event_json, connection=connection
            )
        )


async def pr_check_worker(
    *, webhook_event_json: BlockingZPopReply, connection: RedisConnection
) -> None:
    """
    check status of PR
    If PR can be merged, add to its repo's merge queue
    """
    webhook_event = WebhookEvent.parse_raw(webhook_event_json.value)
    pull_request = PR(
        owner=webhook_event.repo_owner,
        repo=webhook_event.repo_name,
        number=webhook_event.pull_request_number,
        installation_id=webhook_event.installation_id,
    )
    # trigger status updates
    m_res, event = await pull_request.mergeability()
    if event is None or m_res == MergeabilityResponse.NOT_MERGEABLE:
        return
    if m_res not in (
        MergeabilityResponse.NEEDS_UPDATE,
        MergeabilityResponse.NEED_REFRESH,
        MergeabilityResponse.WAIT,
        MergeabilityResponse.OK,
    ):
        raise Exception("Unknown MergeabilityResponse")

    # The following responses are okay to add to merge queue:
    #   + NEEDS_UPDATE - okay for merging
    #   + NEED_REFRESH - assume okay
    #   + WAIT - assume checks pass
    #   + OK - we've got the green
    await redis_webhook_queue.enqueue_for_repo(event=webhook_event)


# TODO(chdsbd): Generalize this event processor boilerplate


async def repo_queue_consumer(
    *, queue_name: str, connection: RedisConnection
) -> typing.NoReturn:
    """
    Worker for a repo given by :queue_name:

    Pull webhook events off redis queue and process for mergeability.

    We only run one of these per repo as we can only merge one PR at a time
    to be efficient. This also alleviates the need of locks.
    """
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("queue", queue_name)
    log = logger.bind(queue=queue_name)
    log.info("start repo_consumer")
    while True:
        log.info("block for new repo event")
        webhook_event_json: BlockingZPopReply = await connection.bzpopmin([queue_name])
        webhook_event = WebhookEvent.parse_raw(webhook_event_json.value)
        pull_request = PR(
            owner=webhook_event.repo_owner,
            repo=webhook_event.repo_name,
            number=webhook_event.pull_request_number,
            installation_id=webhook_event.installation_id,
        )

        while True:
            # there are two exits to this loop:
            # - OK MergeabilityResponse
            # - NOT_MERGEABLE MergeabilityResponse
            #
            # otherwise we continue to poll the Github API for a status change
            # from the other states: NEEDS_UPDATE, NEED_REFRESH, WAIT

            # TODO(chdsbd): Replace enum response with exceptions
            m_res, event = await pull_request.mergeability()
            log = log.bind(res=m_res)
            if event is None or m_res == MergeabilityResponse.NOT_MERGEABLE:
                log.info("cannot merge")
                break
            if m_res == MergeabilityResponse.NEEDS_UPDATE:
                # update pull request and poll for result
                log.info("update pull request and don't attempt to merge")
                await pull_request.update()
                continue
            elif m_res == MergeabilityResponse.NEED_REFRESH:
                # trigger a git mergeability check on Github's end and poll for result
                log.info("needs refresh")
                await pull_request.trigger_mergeability_check()
                continue
            elif m_res == MergeabilityResponse.WAIT:
                # continuously poll until we either get an OK or a failure for mergeability
                log.info("waiting for status checks")
                continue
            elif m_res == MergeabilityResponse.OK:
                # continue to try and merge
                pass
            else:
                raise Exception("Unknown MergeabilityResponse")

            retries = 5
            while retries:
                log.info("merge")
                if await pull_request.merge(event):
                    # success merging
                    break
                retries -= 1
                log.info("retry merge")
                await asyncio.sleep(MERGE_RETRY_RATE_SECONDS)
            else:
                log.error("Exhausted attempts to merge pull request")


QUEUE_SET_NAME = "kodiak_repo_set"


class RedisWebhookQueue:
    connection: asyncio_redis.Connection

    async def create(self) -> None:
        redis_db = 0
        try:
            redis_db = int(conf.REDIS_URL.database)
        except ValueError:
            pass
        self.connection = await asyncio_redis.Pool.create(
            host=conf.REDIS_URL.hostname or "localhost",
            port=conf.REDIS_URL.port or 6379,
            password=conf.REDIS_URL.password or None,
            db=redis_db,
            poolsize=conf.REDIS_POOL_SIZE,
        )

        # restart repo workers
        queues = await self.connection.smembers(QUEUE_SET_NAME)
        for result in queues:
            queue_name = await result
            self.start_repo_worker(queue_name)

        # start webhook worker
        self.start_webhook_worker()

    def start_webhook_worker(self) -> None:
        self._start_worker(
            WEBHOOK_QUEUE_NAME, webhook_event_consumer(connection=self.connection)
        )

    def start_repo_worker(self, queue_name: str) -> None:
        self._start_worker(
            queue_name,
            repo_queue_consumer(queue_name=queue_name, connection=self.connection),
        )

    def _start_worker(self, key: str, fut: typing.Coroutine) -> None:
        worker_task = WORKER_TASKS.get(key)
        if worker_task is not None:
            if not worker_task.done():
                return
            logger.info("task failed")
            # task failed. record result and restart
            exception = worker_task.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
        logger.info("creating task for queue")
        # create new task for queue
        WORKER_TASKS[key] = asyncio.create_task(fut)

    @staticmethod
    def get_queue_key(event: WebhookEvent) -> str:
        return f"kodiak_repo_queue:{event.repo_owner}/{event.repo_name}"

    async def enqueue(self, *, event: WebhookEvent) -> None:
        """
        add :event: to webhook queue
        """
        await self.connection.zadd(WEBHOOK_QUEUE_NAME, {event.json(): time.time()})

    async def enqueue_for_repo(self, *, event: WebhookEvent) -> None:
        """
        1. get the corresponding repo queue for event
        2. add key to QUEUE_SET_NAME so on restart we can recreate the
        worker for the queue.
        3. add event
        4. start worker (will create new worker if one does not exist)
        """
        key = self.get_queue_key(event)
        transaction = await self.connection.multi()
        await transaction.sadd(QUEUE_SET_NAME, [key])
        await transaction.zadd(key, {event.json(): time.time()})
        await transaction.exec()

        self.start_repo_worker(key)


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


redis_webhook_queue = RedisWebhookQueue()


class WebhookEvent(BaseModel):
    repo_owner: str
    repo_name: str
    pull_request_number: int
    installation_id: str


@app.get("/")
async def root() -> str:
    return "OK"


@webhook()
async def pr_event(pr: events.PullRequestEvent) -> None:
    assert pr.installation is not None
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=pr.repository.owner.login,
            repo_name=pr.repository.name,
            pull_request_number=pr.number,
            installation_id=str(pr.installation.id),
        )
    )


@webhook()
async def check_run(check_run_event: events.CheckRunEvent) -> None:
    assert check_run_event.installation
    # Prevent an infinite loop when we update our check run
    if check_run_event.check_run.name == queries.CHECK_RUN_NAME:
        return
    for pr in check_run_event.check_run.pull_requests:
        await redis_webhook_queue.enqueue(
            event=WebhookEvent(
                repo_owner=check_run_event.repository.owner.login,
                repo_name=check_run_event.repository.name,
                pull_request_number=pr.number,
                installation_id=str(check_run_event.installation.id),
            )
        )


@webhook()
async def status_event(status_event: events.StatusEvent) -> None:
    assert status_event.installation
    sha = status_event.commit.sha
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    async with Client(
        owner=owner, repo=repo, installation_id=installation_id
    ) as client:
        prs = await client.get_pull_requests_for_sha(sha=sha)
        if prs is None:
            logger.warning("problem finding prs for sha")
            return None
        for pr in prs:
            await redis_webhook_queue.enqueue(
                event=WebhookEvent(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    installation_id=str(installation_id),
                )
            )


@webhook()
async def pr_review(review: events.PullRequestReviewEvent) -> None:
    assert review.installation
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=review.repository.owner.login,
            repo_name=review.repository.name,
            pull_request_number=review.pull_request.number,
            installation_id=str(review.installation.id),
        )
    )


class MergeabilityResponse(Enum):
    OK = auto()
    NEEDS_UPDATE = auto()
    NEED_REFRESH = auto()
    NOT_MERGEABLE = auto()
    WAIT = auto()


def get_body_content(body_type: BodyText, pull_request: PullRequest) -> str:
    if body_type == BodyText.markdown:
        return pull_request.body
    if body_type == BodyText.plain_text:
        return pull_request.bodyText
    if body_type == BodyText.html:
        return pull_request.bodyHTML
    raise Exception(f"Unknown body_type: {body_type}")


def get_merge_body(config: V1, pull_request: PullRequest) -> dict:
    merge_body: dict = {"merge_method": config.merge.method.value}
    if config.merge.message.body == MergeBodyStyle.pull_request_body:
        body = get_body_content(config.merge.message.body_type, pull_request)
        merge_body.update(dict(commit_message=body))
    if config.merge.message.title == MergeTitleStyle.pull_request_title:
        merge_body.update(dict(commit_title=pull_request.title))
    if config.merge.message.include_pr_number and merge_body.get("commit_title"):
        merge_body["commit_title"] += f" (#{pull_request.number})"
    return merge_body


@dataclass(init=False, repr=False, eq=False)
class PR:
    number: int
    owner: str
    repo: str
    installation_id: str
    log: structlog.BoundLogger
    event: typing.Optional[EventInfoResponse]
    Client: typing.Type[queries.Client] = field(
        default_factory=typing.Type[queries.Client]
    )

    def __eq__(self, b: object) -> bool:
        if not isinstance(b, PR):
            raise NotImplementedError
        return (
            self.number == b.number
            and self.owner == b.owner
            and self.repo == b.repo
            and self.installation_id == b.installation_id
        )

    def __init__(
        self,
        number: int,
        owner: str,
        repo: str,
        installation_id: str,
        Client: typing.Type[queries.Client] = queries.Client,
    ):
        self.number = number
        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        self.Client = Client
        self.log = logger.bind(repo=f"{owner}/{repo}#{number}")

    def __repr__(self) -> str:
        return f"<PR path='{self.owner}/{self.repo}#{self.number}'>"

    async def get_event(self) -> typing.Optional[EventInfoResponse]:
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            default_branch_name = await client.get_default_branch_name()
            if default_branch_name is None:
                return None
            return await client.get_event_info(
                config_file_expression=create_git_revision_expression(
                    branch=default_branch_name, file_path=CONFIG_FILE_PATH
                ),
                pr_number=self.number,
            )

    async def set_status(
        self, summary: str, detail: typing.Optional[str] = None
    ) -> None:
        """
        Display a message to a user through a github check
        """
        if detail is not None:
            message = f"{summary} ({detail})"
        else:
            message = summary
        assert self.event is not None
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            await client.create_notification(
                head_sha=self.event.pull_request.latest_sha,
                message=message,
                summary=None,
            )

    # TODO(chdsbd): Move set_status updates out of this method
    async def mergeability(
        self
    ) -> typing.Tuple[MergeabilityResponse, typing.Optional[EventInfoResponse]]:
        self.log.info("get_event")
        self.event = await self.get_event()
        if self.event is None:
            self.log.info("no event")
            return MergeabilityResponse.NOT_MERGEABLE, None
        if not self.event.head_exists:
            self.log.info("branch deleted")
            return MergeabilityResponse.NOT_MERGEABLE, None
        try:
            self.log.info("check mergeable")
            mergeable(
                config=self.event.config,
                app_id=conf.GITHUB_APP_ID,
                pull_request=self.event.pull_request,
                branch_protection=self.event.branch_protection,
                review_requests_count=self.event.review_requests_count,
                reviews=self.event.reviews,
                contexts=self.event.status_contexts,
                check_runs=self.event.check_runs,
                valid_signature=self.event.valid_signature,
                valid_merge_methods=self.event.valid_merge_methods,
            )
            self.log.info("okay")
            return MergeabilityResponse.OK, self.event
        except MissingAppID:
            return MergeabilityResponse.NOT_MERGEABLE, self.event
        except NotQueueable as e:
            await self.set_status(summary="🛑 cannot merge", detail=str(e))
            return MergeabilityResponse.NOT_MERGEABLE, self.event
        except MergeConflict:
            await self.set_status(summary="🛑 cannot merge", detail="merge conflict")
            if self.event.config.merge.notify_on_conflict:
                await self.notify_pr_creator()
            return MergeabilityResponse.NOT_MERGEABLE, self.event
        except MissingGithubMergeabilityState:
            self.log.info("missing mergeability state, need refresh")
            return MergeabilityResponse.NEED_REFRESH, self.event
        except WaitingForChecks:
            await self.set_status(summary="⏳ waiting for checks")
            return MergeabilityResponse.WAIT, self.event
        except NeedsBranchUpdate:
            await self.set_status(summary="⏭ need update")
            return MergeabilityResponse.NEEDS_UPDATE, self.event
        except BranchMerged:
            await self.set_status(
                summary="🛑 cannot merge", detail="branch merged already"
            )
            if self.event.config.merge.delete_branch_on_merge:
                async with self.Client(
                    owner=self.owner,
                    repo=self.repo,
                    installation_id=self.installation_id,
                ) as client:
                    await client.delete_branch(
                        branch=self.event.pull_request.headRefName
                    )
            return MergeabilityResponse.NOT_MERGEABLE, self.event

    async def update(self) -> None:
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            self.log.info("update")
            event = await self.get_event()
            if event is None:
                self.log.warning("problem")
                return
            await client.merge_branch(
                head=event.pull_request.baseRefName, base=event.pull_request.headRefName
            )

    async def trigger_mergeability_check(self) -> None:
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            await client.get_pull_request(number=self.number)

    async def merge(self, event: EventInfoResponse) -> bool:
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            res = await client.merge_pull_request(
                number=self.number,
                body=get_merge_body(event.config, event.pull_request),
            )
            return not res.status_code > 300

    async def delete_label(self, label: str) -> bool:
        """
        remove the PR label specified by `label_id` for a given `pr_number`
        """
        self.log.info("deleting label", label=label)
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            headers = await client.get_headers(self.installation_id)
            res = await client.session.delete(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}/labels/{label}",
                headers=headers,
            )
            return typing.cast(bool, res.status_code != 204)

    async def create_comment(self, body: str) -> bool:
        """
        create a comment on the speicifed `pr_number` with the given `body` as text.
        """
        self.log.info("creating comment", body=body)
        async with self.Client(
            owner=self.owner, repo=self.repo, installation_id=self.installation_id
        ) as client:
            headers = await client.get_headers(self.installation_id)
            res = await client.session.post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}/comments",
                json=dict(body=body),
                headers=headers,
            )
            return typing.cast(bool, res.status_code != 200)

    async def notify_pr_creator(self) -> bool:
        """
        comment on PR with an `@$PR_CREATOR_NAME` and remove `automerge` label.

        Since we don't have atomicity we chose to remove the label first
        instead of creating the comment first as we would rather have no
        comment instead of multiple comments on each consecutive PR push.
        """

        event = self.event
        if not event:
            return False
        label = event.config.merge.automerge_label
        if not await self.delete_label(label=label):
            return False

        # TODO(sbdchd): add mentioning of PR author in comment.
        body = textwrap.dedent(
            """
        This PR currently has a merge conflict. Please resolve this and then re-add the `automerge` label.
        """
        )
        return await self.create_comment(body)


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()
