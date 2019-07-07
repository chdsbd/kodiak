from __future__ import annotations

import asyncio
import time
import typing

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
from kodiak.github import Webhook, events
from kodiak.pull_request import PR, MergeabilityResponse
from kodiak.queries import Client

sentry_sdk.init()

app = FastAPI()
app.add_middleware(SentryMiddleware)

webhook = Webhook(app)
logger = structlog.get_logger()

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
        asyncio.create_task(pr_check_worker(webhook_event_json=webhook_event_json))


async def pr_check_worker(*, webhook_event_json: BlockingZPopReply) -> None:
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


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()
