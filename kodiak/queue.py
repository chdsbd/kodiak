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


T = typing.TypeVar("T")


def find_position(x: typing.Iterable[T], v: T) -> typing.Optional[int]:
    count = 0
    for item in x:
        if item == v:
            return count
        count += 1
    return None


async def update_pr_immediately_if_configured(
    m_res: MergeabilityResponse,
    event: EventInfoResponse,
    pull_request: PR,
    log: structlog.BoundLogger,
) -> None:
    if (
        m_res == MergeabilityResponse.NEEDS_UPDATE
        and isinstance(event.config, V1)
        and event.config.merge.update_branch_immediately
    ):
        log.info("updating pull request")
        await pull_request.set_status(summary="🔄 attempting to update pull request")
        if not await update_pr_with_retry(pull_request):
            log.error("failed to update branch")
            await pull_request.set_status(summary="🛑 could not update branch")
        # we don't need to overwrite the "attempting to update..." message here
        # because it will be updated by either the merge queue logic or the
        # `merge.do_not_merge` logic.


async def process_webhook_event(
    connection: RedisConnection,
    webhook_queue: RedisWebhookQueue,
    queue_name: str,
    log: structlog.BoundLogger,
) -> None:
    log.info("block for new webhook event")
    webhook_event_json: BlockingZPopReply = await connection.bzpopmin([queue_name])
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
        is_merging = (
            await connection.get(webhook_event.get_merge_target_queue_name())
            == webhook_event.json()
        )
        # trigger status updates
        m_res, event = await pull_request.mergeability()
        if event is None or m_res == MergeabilityResponse.NOT_MERGEABLE:
            # remove ineligible events from the merge queue
            await connection.zrem(
                webhook_event.get_merge_queue_name(), [webhook_event.json()]
            )
            return
        if m_res == MergeabilityResponse.SKIPPABLE_CHECKS:
            log.info("skippable checks")
            return
        await update_pr_immediately_if_configured(m_res, event, pull_request, log)

        if m_res not in (
            MergeabilityResponse.NEEDS_UPDATE,
            MergeabilityResponse.NEED_REFRESH,
            MergeabilityResponse.WAIT,
            MergeabilityResponse.OK,
            MergeabilityResponse.SKIPPABLE_CHECKS,
        ):
            raise Exception("Unknown MergeabilityResponse")

        if (
            isinstance(event.config, V1)
            and event.config.merge.do_not_merge
        ):
            log.debug("skipping merging for PR because `merge.do_not_merge` is configured.")
            await pull_request.set_status(summary="✅ okay to merge")
            return

        if (
            isinstance(event.config, V1)
            and event.config.merge.prioritize_ready_to_merge
            and m_res == MergeabilityResponse.OK
        ):
            merge_success = await pull_request.merge(event)
            if merge_success:
                return
            log.error("problem merging PR")

        # don't clobber statuses set in the merge loop
        # The following responses are okay to add to merge queue:
        #   + NEEDS_UPDATE - okay for merging
        #   + NEED_REFRESH - assume okay
        #   + WAIT - assume checks pass
        #   + OK - we've got the green
        webhook_event_jsons = await webhook_queue.enqueue_for_repo(event=webhook_event)
        if is_merging:
            return

        position = find_position(webhook_event_jsons, webhook_event_json.value)
        if position is None:
            return
        # use 1-based indexing
        humanized_position = inflection.ordinalize(position + 1)
        await pull_request.set_status(
            f"📦 enqueued for merge (position={humanized_position})"
        )


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


async def update_pr_with_retry(pull_request: PR) -> bool:
    # try multiple times in case of intermittent failure
    retries = 5
    while retries:
        update_ok = await pull_request.update()
        if update_ok:
            return True
        retries -= 1
        await asyncio.sleep(RETRY_RATE_SECONDS)
    return False


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

        # mark that we're working on this PR
        await pull_request.set_status(summary="⛴ attempting to merge PR")
        skippable_check_timeout = 4
        while True:
            # there are two exits to this loop:
            # - OK MergeabilityResponse
            # - NOT_MERGEABLE MergeabilityResponse
            #
            # otherwise we continue to poll the Github API for a status change
            # from the other states: NEEDS_UPDATE, NEED_REFRESH, WAIT

            # TODO(chdsbd): Replace enum response with exceptions
            m_res, event = await pull_request.mergeability(merging=True)
            log = log.bind(res=m_res)
            if event is None or m_res == MergeabilityResponse.NOT_MERGEABLE:
                log.info("cannot merge")
                break
            if m_res == MergeabilityResponse.SKIPPABLE_CHECKS:
                if skippable_check_timeout:
                    skippable_check_timeout -= 1
                    await asyncio.sleep(RETRY_RATE_SECONDS)
                    continue
                await pull_request.set_status(
                    summary="⌛️ waiting a bit for skippable checks"
                )
                break

            if m_res == MergeabilityResponse.NEEDS_UPDATE:
                log.info("update pull request and don't attempt to merge")

                if await update_pr_with_retry(pull_request):
                    continue
                log.error("failed to update branch")
                await pull_request.set_status(summary="🛑 could not update branch")
                # break to find next PR to try and merge
                break
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
                await asyncio.sleep(RETRY_RATE_SECONDS)
            else:
                log.error("Exhausted attempts to merge pull request")


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
