from __future__ import annotations

import asyncio
import time
import typing
import urllib
from typing import Optional

import asyncio_redis
import sentry_sdk
import structlog
from asyncio_redis.connection import Connection as RedisConnection
from asyncio_redis.replies import BlockingZPopReply
from pydantic import BaseModel

import kodiak.app_config as conf
from kodiak.pull_request import evaluate_pr

logger = structlog.get_logger()


MERGE_QUEUE_NAMES = "kodiak_merge_queue_names:v2"
WEBHOOK_QUEUE_NAMES = "kodiak_webhook_queue_names"

WORKER_TASKS: typing.MutableMapping[str, asyncio.Task[None]] = {}

RETRY_RATE_SECONDS = 2


class WebhookEvent(BaseModel):
    repo_owner: str
    repo_name: str
    pull_request_number: int
    installation_id: str
    target_name: str

    def get_merge_queue_name(self) -> str:
        return get_merge_queue_name(self)

    def get_merge_target_queue_name(self) -> str:
        return self.get_merge_queue_name() + ":target"

    def get_webhook_queue_name(self) -> str:
        return get_webhook_queue_name(self)

    def __hash__(self) -> int:
        return (
            hash(self.repo_owner)
            + hash(self.repo_name)
            + hash(self.pull_request_number)
            + hash(self.installation_id)
        )


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
    is_active_merging = (
        await connection.get(webhook_event.get_merge_target_queue_name())
        == webhook_event.json()
    )

    async def dequeue() -> None:
        await connection.zrem(
            webhook_event.get_merge_queue_name(), [webhook_event.json()]
        )

    async def requeue() -> None:
        await connection.zadd(
            webhook_event.get_webhook_queue_name(),
            {webhook_event.json(): time.time()},
            only_if_not_exists=True,
        )

    async def queue_for_merge(*, first: bool) -> Optional[int]:
        return await webhook_queue.enqueue_for_repo(event=webhook_event, first=first)

    log.info("evaluate pr for webhook event")
    await evaluate_pr(
        install=webhook_event.installation_id,
        owner=webhook_event.repo_owner,
        repo=webhook_event.repo_name,
        number=webhook_event.pull_request_number,
        merging=False,
        dequeue_callback=dequeue,
        requeue_callback=requeue,
        queue_for_merge_callback=queue_for_merge,
        is_active_merging=is_active_merging,
    )


async def webhook_event_consumer(
    *, connection: RedisConnection, webhook_queue: RedisWebhookQueue, queue_name: str
) -> typing.NoReturn:
    """
    Worker to process incoming webhook events from redis

    1. process mergeability information and update github check status for pr
    2. enqueue pr into repo queue for merging, if mergeability passed
    """

    # We need to define a custom Hub so that we can set the scope correctly.
    # Without creating a new hub we end up overwriting the scopes of other
    # consumers.
    #
    # https://github.com/getsentry/sentry-python/issues/147#issuecomment-432959196
    # https://github.com/getsentry/sentry-python/blob/0da369f839ee2c383659c91ea8858abcac04b869/sentry_sdk/integrations/aiohttp.py#L80-L83
    # https://github.com/getsentry/sentry-python/blob/464ca8dda09155fcc43dfbb6fa09cf00313bf5b8/sentry_sdk/integrations/asgi.py#L90-L113
    with sentry_sdk.Hub(sentry_sdk.Hub.current) as hub:
        with hub.configure_scope() as scope:
            scope.set_tag("queue", queue_name)
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

    async def dequeue() -> None:
        await connection.zrem(
            webhook_event.get_merge_queue_name(), [webhook_event.json()]
        )

    async def requeue() -> None:
        await connection.zadd(
            webhook_event.get_webhook_queue_name(),
            {webhook_event.json(): time.time()},
            only_if_not_exists=True,
        )

    async def queue_for_merge(*, first: bool) -> Optional[int]:
        raise NotImplementedError

    log.info("evaluate PR for merging")
    await evaluate_pr(
        install=webhook_event.installation_id,
        owner=webhook_event.repo_owner,
        repo=webhook_event.repo_name,
        number=webhook_event.pull_request_number,
        dequeue_callback=dequeue,
        requeue_callback=requeue,
        merging=True,
        is_active_merging=False,
        queue_for_merge_callback=queue_for_merge,
    )


async def repo_queue_consumer(
    *, queue_name: str, connection: RedisConnection
) -> typing.NoReturn:
    """
    Worker for a repo given by :queue_name:

    Pull webhook events off redis queue and process for mergeability.

    We only run one of these per repo as we can only merge one PR at a time
    to be efficient. This also alleviates the need of locks.
    """
    with sentry_sdk.Hub(sentry_sdk.Hub.current) as hub:
        with hub.configure_scope() as scope:
            scope.set_tag("queue", queue_name)
        log = logger.bind(queue=queue_name)
        log.info("start repo_consumer")
        while True:
            await process_repo_queue(log, connection, queue_name)


T = typing.TypeVar("T")


def find_position(x: typing.Iterable[T], v: T) -> typing.Optional[int]:
    count = 0
    for item in x:
        if item == v:
            return count
        count += 1
    return None


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

    def _start_worker(self, key: str, fut: typing.Coroutine[None, None, None]) -> None:
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
        log = logger.bind(
            owner=event.repo_owner,
            repo=event.repo_name,
            number=event.pull_request_number,
            install=event.installation_id,
        )
        log.info("enqueue webhook event")
        self.start_webhook_worker(queue_name=queue_name)

    async def enqueue_for_repo(
        self, *, event: WebhookEvent, first: bool
    ) -> Optional[int]:
        """
        1. get the corresponding repo queue for event
        2. add key to MERGE_QUEUE_NAMES so on restart we can recreate the
        worker for the queue.
        3. add event
        4. start worker (will create new worker if one does not exist)

        returns position of event in queue
        """
        queue_name = get_merge_queue_name(event)
        transaction = await self.connection.multi()
        await transaction.sadd(MERGE_QUEUE_NAMES, [queue_name])
        if first:
            # place at front of queue. To allow us to always place this PR at
            # the front, we should not pass only_if_not_exists.
            await transaction.zadd(queue_name, {event.json(): 1.0})
        else:
            # use only_if_not_exists to prevent changing queue positions on new
            # webhook events.
            await transaction.zadd(
                queue_name, {event.json(): time.time()}, only_if_not_exists=True
            )
        future_results = await transaction.zrange(queue_name, 0, 1000)
        await transaction.exec()
        log = logger.bind(
            owner=event.repo_owner,
            repo=event.repo_name,
            number=event.pull_request_number,
            install=event.installation_id,
        )

        log.info("enqueue repo event")
        self.start_repo_worker(queue_name)
        results = await future_results
        dictionary = await results.asdict()
        kvs = sorted(
            ((key, value) for key, value in dictionary.items()), key=lambda x: x[1]
        )
        return find_position((key for key, value in kvs), event.json())


def get_merge_queue_name(event: WebhookEvent) -> str:
    escaped_target = urllib.parse.quote(event.target_name)
    return f"merge_queue:{event.installation_id}.{event.repo_owner}/{event.repo_name}/{escaped_target}"


def get_webhook_queue_name(event: WebhookEvent) -> str:
    return f"webhook:{event.installation_id}"


redis_webhook_queue = RedisWebhookQueue()
