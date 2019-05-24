from __future__ import annotations

import asyncio
import os
import typing
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto

import sentry_sdk
import structlog
from fastapi import FastAPI
from sentry_asgi import SentryMiddleware

from kodiak import queries
from kodiak.config import V1, MergeBodyStyle, MergeTitleStyle
from kodiak.evaluation import (
    MissingGithubMergabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
    mergable,
)
from kodiak.github import Webhook, events
from kodiak.queries import Client, EventInfoResponse, PullRequest

if not os.environ.get("DEBUG"):
    sentry_sdk.init(dsn="https://8ccee0e2ac584ed78483ad51868db0a2@sentry.io/1464537")

app = FastAPI()
app.add_middleware(SentryMiddleware)

webhook = Webhook(app)
logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"

processing_queue: "asyncio.Queue[Event]" = asyncio.Queue()


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


@dataclass
class Event:
    repo_owner: str
    repo_name: str
    source_event: events.GithubEvent
    pull_request_number: int
    installation_id: str


@app.get("/")
async def root() -> str:
    return "OK"


@webhook()
async def pr_event(pr: events.PullRequestEvent) -> None:
    assert pr.installation is not None
    processing_queue.put_nowait(
        Event(
            repo_owner=pr.repository.owner.login,
            repo_name=pr.repository.name,
            pull_request_number=pr.number,
            source_event=pr,
            installation_id=str(pr.installation.id),
        )
    )


@webhook()
async def check_run(check_run_event: events.CheckRunEvent) -> None:
    assert check_run_event.installation
    owner = check_run_event.repository.owner.login
    repo = check_run_event.repository.name
    installation_id = check_run_event.installation.id
    for pr in check_run_event.check_run.pull_requests:
        processing_queue.put_nowait(
            Event(
                repo_owner=owner,
                repo_name=repo,
                pull_request_number=pr.number,
                source_event=check_run_event,
                installation_id=str(installation_id),
            )
        )


@webhook()
async def status_event(status_event: events.StatusEvent) -> None:
    assert status_event.installation
    sha = status_event.commit.sha
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    async with Client() as client:
        prs = await client.get_pull_requests_for_sha(
            owner=owner, repo=repo, installation_id=installation_id, sha=sha
        )
        if prs is None:
            logger.warning("problem finding prs for sha")
            return None
        for pr in prs:
            processing_queue.put_nowait(
                Event(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    source_event=status_event,
                    installation_id=installation_id,
                )
            )


@webhook()
async def pr_review(review: events.PullRequestReviewEvent) -> None:
    assert review.installation
    owner = review.repository.owner.login
    repo = review.repository.name
    installation_id = review.installation.id
    pr = review.pull_request
    processing_queue.put_nowait(
        Event(
            repo_owner=owner,
            repo_name=repo,
            pull_request_number=pr.number,
            source_event=review,
            installation_id=str(installation_id),
        )
    )


@dataclass
class RepoQueue:
    lock: asyncio.Lock = asyncio.Lock()
    queue: typing.Deque[PR] = deque()
    _waiters: typing.List[asyncio.Future] = field(default_factory=list)

    async def __getitem__(self, index: int) -> PR:
        try:
            return self.queue[index]
        except IndexError:
            fut: "asyncio.Future[PR]" = asyncio.get_event_loop().create_future()
            self._waiters.append(fut)
            return await fut

    async def enqueue(self, pr: PR) -> None:
        async with self.lock:
            if pr not in self.queue:
                # TODO: Is there a bug here by adding the item to the queue and returning it in the future?
                self.queue.append(pr)
                try:
                    fut = self._waiters.pop(0)
                    fut.set_result(pr)
                except IndexError:
                    pass

    async def dequeue(self, pr: PR) -> None:
        async with self.lock:
            try:
                self.queue.remove(pr)
            except ValueError:
                # pr is not in queue
                pass


class MergeabilityResponse(Enum):
    OK = auto()
    NEEDS_UPDATE = auto()
    NEED_REFRESH = auto()
    NOT_MERGEABLE = auto()
    WAIT = auto()


class MergeResults(Enum):
    OK = auto()
    CANNOT_MERGE = auto()
    API_FAILURE = auto()


@dataclass(init=False, repr=False, eq=False)
class PR:
    number: int
    owner: str
    repo: str
    installation_id: str
    log: structlog.BoundLogger
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
        async with self.Client() as client:
            default_branch_name = await client.get_default_branch_name(
                owner=self.owner, repo=self.repo, installation_id=self.installation_id
            )
            if default_branch_name is None:
                return None
            return await client.get_event_info(
                owner=self.owner,
                repo=self.repo,
                config_file_expression=create_git_revision_expression(
                    branch=default_branch_name, file_path=CONFIG_FILE_PATH
                ),
                pr_number=self.number,
                installation_id=self.installation_id,
            )

    async def mergability(
        self
    ) -> typing.Tuple[MergeabilityResponse, typing.Optional[EventInfoResponse]]:
        event = await self.get_event()
        if event is None:
            return MergeabilityResponse.NOT_MERGEABLE, None
        try:
            mergable(
                config=event.config,
                pull_request=event.pull_request,
                branch_protection=event.branch_protection,
                review_requests_count=event.review_requests_count,
                reviews=event.reviews,
                contexts=event.status_contexts,
                check_runs=event.check_runs,
                valid_signature=event.valid_signature,
                valid_merge_methods=event.valid_merge_methods,
            )
            return MergeabilityResponse.OK, event
        except NotQueueable:
            return MergeabilityResponse.NOT_MERGEABLE, event
        except MissingGithubMergabilityState:
            return MergeabilityResponse.NEED_REFRESH, event
        except WaitingForChecks:
            return MergeabilityResponse.WAIT, event
        except NeedsBranchUpdate:
            return MergeabilityResponse.NEEDS_UPDATE, event

    async def update(self) -> None:
        async with self.Client() as client:
            event = await self.get_event()
            if event is None:
                self.log.warning("problem")
                return
            token = await client.get_token_for_install(
                installation_id=self.installation_id
            )
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )
            await client.session.post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/merges",
                json=dict(
                    head=event.pull_request.baseRefName,
                    base=event.pull_request.headRefName,
                ),
                headers=headers,
            )

    @staticmethod
    def get_merge_body(config: V1, pull_request: PullRequest) -> dict:
        merge_body: dict = {"merge_method": config.merge.method.value}
        if config.merge.message.body == MergeBodyStyle.pull_request_body:
            merge_body.update(dict(commit_message=pull_request.bodyText))
        if config.merge.message.title == MergeTitleStyle.pull_request_title:
            merge_body.update(dict(commit_title=pull_request.title))
        if config.merge.message.include_pr_number and merge_body.get("commit_title"):
            merge_body["commit_title"] += f" ({pull_request.number})"
        return merge_body

    async def merge(self) -> MergeResults:
        m_res, event = await self.mergability()
        log = self.log.bind(merge_response=m_res)
        if m_res == MergeabilityResponse.NEEDS_UPDATE:
            await self.update()
        elif m_res == MergeabilityResponse.OK:
            pass
        elif m_res == MergeabilityResponse.NEED_REFRESH:
            pass
        elif m_res == MergeabilityResponse.WAIT:
            pass
        else:
            log.warning("Couldn't merge PR")
            return MergeResults.CANNOT_MERGE
        if event is None:
            return MergeResults.CANNOT_MERGE
        async with self.Client() as client:
            token = await client.get_token_for_install(
                installation_id=self.installation_id
            )
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )

            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.number}/merge"
            res = await client.session.put(
                url,
                headers=headers,
                json=self.get_merge_body(event.config, event.pull_request),
            )
            log.info("merge attempt", res=res, res_json=res.json())
            if res.status_code < 300:
                return MergeResults.OK
            return MergeResults.API_FAILURE


class Retry:
    pass


@dataclass
class RepoWorker:
    q: RepoQueue
    task: asyncio.Task
    Client: typing.Type[queries.Client] = queries.Client

    async def ingest(self, pr: PR) -> typing.Optional[Retry]:
        log = logger.bind(repo=f"{pr.owner}/{pr.repo}", pr_number=pr.number)
        # IF PR needs an update or can be merged, add it to queue
        mergability, _event = await pr.mergability()
        if mergability in (
            MergeabilityResponse.OK,
            MergeabilityResponse.NEEDS_UPDATE,
            MergeabilityResponse.WAIT,
        ):
            log.info("queuing", mergability=mergability)
            await self.q.enqueue(pr)
        elif mergability == MergeabilityResponse.NEED_REFRESH:
            log.info("Need to trigger update")
            async with self.Client() as client:
                token = await client.get_token_for_install(
                    installation_id=pr.installation_id
                )
                headers = dict(
                    Authorization=f"token {token}",
                    Accept="application/vnd.github.machine-man-preview+json",
                )
                url = f"https://api.github.com/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"
                await client.session.get(url, headers=headers)
            return Retry()

        else:
            log.info("cannot queue", mergability=mergability)
        return None


REPO_QUEUES: typing.MutableMapping[str, RepoWorker] = dict()
MERGE_SLEEP_SECONDS = 3


async def _work_repo_queue(q: RepoQueue) -> None:
    log = logger.bind(queue=q.queue)
    log.info("processing start")
    first = await q[0]
    log = log.bind(pr=first)
    async with q.lock:
        res = await first.merge()
        if res == MergeResults.OK:
            log.info("Merged. POP FROM QUEUE")
            q.queue.popleft()
        elif res == MergeResults.CANNOT_MERGE:
            log.info("Cannot merge. REMOVE FROM QUEUE")
            q.queue.popleft()
        else:
            await asyncio.sleep(MERGE_SLEEP_SECONDS)
            log.warning("problem merging")
        log.info("processing finished")


async def work_repo_queue(q: RepoQueue) -> typing.NoReturn:
    while True:
        await _work_repo_queue(q)


def get_queue_for_repo(owner: str, repo: str, installation_id: str) -> RepoWorker:
    id = f"{owner}/{repo}"
    rq = REPO_QUEUES.get(id)
    if rq is None:
        logger.info("could not find queue for repo")
        q = RepoQueue()
        task = asyncio.create_task(work_repo_queue(q))
        rq = RepoWorker(q=q, task=task)
        REPO_QUEUES[id] = rq
    # check if we had a problem with the task and restart
    if rq.task.done():
        exception = rq.task.exception()
        sentry_sdk.capture_exception(exception)
        logger.info("task done", task_exception=exception)
        rq.task = asyncio.create_task(work_repo_queue(rq.q))
    return rq


async def event_processor(webhook_queue: "asyncio.Queue[Event]") -> typing.NoReturn:
    """
    - Lookup info for pull request
    - Should we add the pull request to be queued to updated/merged?

    - for a repos queue, while it's non-empty, loop.
    - take first PR, check it's mergability
        + update if necessary
        + remove from queue if no longer valid
        + merge PR
    """
    logger.info("event processor started")
    while True:
        github_event: "Event" = await webhook_queue.get()
        owner = github_event.repo_owner
        repo = github_event.repo_name
        pr_number = github_event.pull_request_number
        installation_id = github_event.installation_id
        log = logger.bind(
            installation_id=installation_id, owner=owner, repo=repo, pr_number=pr_number
        )
        log.info("pull event from queue for processing")
        repo_queue = get_queue_for_repo(
            owner=owner, repo=repo, installation_id=installation_id
        )
        res = await repo_queue.ingest(
            PR(
                owner=owner,
                repo=repo,
                number=pr_number,
                installation_id=installation_id,
            )
        )
        if isinstance(res, Retry):
            # add some delay for things to settle on Github's end
            await asyncio.sleep(1)
            webhook_queue.put_nowait(github_event)


EVENT_PROCESSOR: typing.Optional[asyncio.Task] = None


async def task_manager() -> typing.NoReturn:
    # pylint: disable=global-statement
    global EVENT_PROCESSOR
    while True:
        if (
            EVENT_PROCESSOR is not None
            and EVENT_PROCESSOR.done()
            and EVENT_PROCESSOR.exception()
        ):
            task_exception = EVENT_PROCESSOR.exception()
            sentry_sdk.capture_exception(task_exception)
            logger.warning("event_processor failed", task_exception=task_exception)
            EVENT_PROCESSOR = asyncio.create_task(event_processor(processing_queue))
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup() -> None:
    # pylint: disable=global-statement
    global EVENT_PROCESSOR
    EVENT_PROCESSOR = asyncio.create_task(event_processor(processing_queue))
    asyncio.create_task(task_manager())


@app.on_event("shutdown")
async def shutdown() -> None:
    ...
