from __future__ import annotations

import asyncio
import time
import typing

import asyncio_redis
import inflection
import sentry_sdk
import structlog
from asyncio_redis.connection import Connection as RedisConnection
from asyncio_redis.replies import BlockingZPopReply
from pydantic import BaseModel

import kodiak.app_config as conf
from kodiak.config import V1
from kodiak.pull_request import PR, EventInfoResponse, MergeabilityResponse
from kodiak.queries import Client

logger = structlog.get_logger()


MERGE_QUEUE_NAMES = "kodiak_merge_queue_names"
WEBHOOK_QUEUE_NAMES = "kodiak_webhook_queue_names"

WORKER_TASKS: typing.MutableMapping[str, asyncio.Task] = {}

RETRY_RATE_SECONDS = 2


class WebhookEvent(BaseModel):
    repo_owner: str
    repo_name: str
    pull_request_number: int
    installation_id: str

    def get_merge_queue_name(self) -> str:
        return get_merge_queue_name(self)

    def get_merge_target_queue_name(self) -> str:
        return self.get_merge_queue_name() + ":target"


async def process_webhook_event(
    connection: RedisConnection,
    webhook_queue: RedisWebhookQueue,
    queue_name: str,
    log: structlog.BoundLogger,
) -> None:
    log.info("block for new webhook event")
    webhook_event_json: BlockingZPopReply = await connection.bzpopmin([queue_name])
    log.info("parsing webhook event")
    webhook_event = WebhookEvent.parse_raw(webhook_event_json.value)
    async with Client(
        owner=webhook_event.repo_owner,
        repo=webhook_event.repo_name,
        installation_id=webhook_event.installation_id,
    ) as api_client:
        pull_request = PR(
            owner=webhook_event.repo_owner,
            repo=webhook_event.repo_name,
            number=webhook_event.pull_request_number,
            installation_id=webhook_event.installation_id,
            client=api_client,
        )
        await pull_request.evaluate_mergeability()


async def webhook_event_consumer(
    *, connection: RedisConnection, webhook_queue: RedisWebhookQueue, queue_name: str
) -> typing.NoReturn:
    """
    Worker to process incoming webhook events from redis

    1. process mergeability information and update github check status for pr
    2. enqueue pr into repo queue for merging, if mergeability passed
    """
    log = logger.bind(queue=queue_name)
    log.info("start webhook event consumer")

    while True:
        await process_webhook_event(connection, webhook_queue, queue_name, log)


async def process_repo_queue(
    log: structlog.BoundLogger, connection: RedisConnection, queue_name: str
) -> None:
    log.info("block for new repo event")
    webhook_event_json: BlockingZPopReply = await connection.bzpopmin([queue_name])
    webhook_event = WebhookEvent.parse_raw(webhook_event_json.value)
    # mark this PR as being merged currently. we check this elsewhere to set proper status codes
    await connection.set(
        webhook_event.get_merge_target_queue_name(), webhook_event.json()
    )
    async with Client(
        owner=webhook_event.repo_owner,
        repo=webhook_event.repo_name,
        installation_id=webhook_event.installation_id,
    ) as api_client:
        pull_request = PR(
            owner=webhook_event.repo_owner,
            repo=webhook_event.repo_name,
            number=webhook_event.pull_request_number,
            installation_id=webhook_event.installation_id,
            client=api_client,
        )
        await pull_request.evaluate_mergeability(merging=True)


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
        await process_repo_queue(log, connection, queue_name)


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
        merge_queues, webhook_queues = await asyncio.gather(
            self.connection.smembers(MERGE_QUEUE_NAMES),
            self.connection.smembers(WEBHOOK_QUEUE_NAMES),
        )
        for merge_result in merge_queues:
            queue_name = await merge_result
            self.start_repo_worker(queue_name)

        for webhook_result in webhook_queues:
            queue_name = await webhook_result
            self.start_webhook_worker(queue_name=queue_name)

    def start_webhook_worker(self, *, queue_name: str) -> None:
        self._start_worker(
            queue_name,
            webhook_event_consumer(
                connection=self.connection, webhook_queue=self, queue_name=queue_name
            ),
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

    async def enqueue(self, *, event: WebhookEvent) -> None:
        """
        add :event: to webhook queue
        """
        queue_name = get_webhook_queue_name(event)
        transaction = await self.connection.multi()
        await transaction.sadd(WEBHOOK_QUEUE_NAMES, [queue_name])
        await transaction.zadd(
            queue_name, {event.json(): time.time()}, only_if_not_exists=True
        )
        await transaction.exec()

        self.start_webhook_worker(queue_name=queue_name)

    async def enqueue_for_repo(self, *, event: WebhookEvent) -> typing.List[str]:
        """
        1. get the corresponding repo queue for event
        2. add key to MERGE_QUEUE_NAMES so on restart we can recreate the
        worker for the queue.
        3. add event
        4. start worker (will create new worker if one does not exist)
        """
        key = get_merge_queue_name(event)
        transaction = await self.connection.multi()
        await transaction.sadd(MERGE_QUEUE_NAMES, [key])
        await transaction.zadd(
            key, {event.json(): time.time()}, only_if_not_exists=True
        )
        future_results = await transaction.zrange(key, 0, 1000)
        await transaction.exec()

        self.start_repo_worker(key)
        results = await future_results
        dictionary = await results.asdict()
        kvs = sorted(
            ((key, value) for key, value in dictionary.items()), key=lambda x: x[1]
        )
        return [key for key, value in kvs]


def get_merge_queue_name(event: WebhookEvent) -> str:
    return f"merge_queue:{event.installation_id}.{event.repo_owner}/{event.repo_name}"


def get_webhook_queue_name(event: WebhookEvent) -> str:
    return f"webhook:{event.installation_id}"
