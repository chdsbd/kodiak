"""
Process webhook events from the Redis queues.
"""
from __future__ import annotations

import asyncio
from asyncio.tasks import Task
from typing import NoReturn

import pydantic
import sentry_sdk
import structlog

from kodiak import app_config as conf
from kodiak.assertions import assert_never
from kodiak.logging import configure_logging
from kodiak.queue import (
    INGEST_QUEUE_NAMES,
    QUEUE_PUBSUB_INGEST,
    RedisWebhookQueue,
    WebhookQueueProtocol,
    get_ingest_queue,
    handle_webhook_event,
)
from kodiak.redis_client import redis_bot
from kodiak.schemas import RawWebhookEvent

configure_logging()

logger = structlog.get_logger()


async def work_ingest_queue(queue: WebhookQueueProtocol, queue_name: str) -> NoReturn:
    log = logger.bind(queue_name=queue_name, task="work_ingest_queue")

    log.info("start working ingest_queue")
    while True:
        res = await redis_bot.blpop(
            [queue_name], timeout=conf.REDIS_BLOCKING_POP_TIMEOUT_SEC
        )
        if res is None:
            continue
        _, value = res
        parsed_event = RawWebhookEvent.parse_raw(value)
        await handle_webhook_event(
            queue=queue,
            event_name=parsed_event.event_name,
            payload=parsed_event.payload,
        )
        log.info("ingest_event_handled")


class PubsubIngestQueueSchema(pydantic.BaseModel):
    installation_id: int


async def ingest_queue_starter(
    ingest_workers: dict[str, Task[NoReturn]], queue: RedisWebhookQueue
) -> None:
    """
    Listen on Redis Pubsub and start queue worker if we don't have one already.
    """
    pubsub = redis_bot.pubsub()
    await pubsub.subscribe(QUEUE_PUBSUB_INGEST)
    log = logger.bind(task="ingest_queue_starter")
    log.info("start watch for ingest_queues")
    while True:
        reply = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10)
        if reply is None:
            continue
        installation_id = PubsubIngestQueueSchema.parse_raw(
            reply["data"]
        ).installation_id
        queue_name = get_ingest_queue(installation_id)
        if queue_name not in ingest_workers:
            ingest_workers[queue_name] = asyncio.create_task(
                work_ingest_queue(queue, queue_name=queue_name)
            )
            log.info("started new task")


async def main() -> NoReturn:
    queue = RedisWebhookQueue()
    await queue.create()

    ingest_workers = dict()

    ingest_queue_names = await redis_bot.smembers(INGEST_QUEUE_NAMES)
    log = logger.bind(task="main_worker")

    for queue_name_bytes in ingest_queue_names:
        queue_name = queue_name_bytes.decode()
        if queue_name not in ingest_workers:
            log.info("start ingest_queue_worker", queue_name=queue_name)
            ingest_workers[queue_name] = asyncio.create_task(
                work_ingest_queue(queue, queue_name=queue_name)
            )

    log.info("start ingest_queue_watcher")
    ingest_queue_watcher = asyncio.create_task(
        ingest_queue_starter(ingest_workers, queue)
    )

    while True:
        # Health check the various tasks and recreate them if necessary.
        # There's probably a cleaner way to do this.
        await asyncio.sleep(0.25)
        for queue_name, worker_task in ingest_workers.items():
            if worker_task is None or not worker_task.done():
                continue
            logger.info("worker task failed", kind="ingest")
            # task failed. record result and restart
            exception = worker_task.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
            ingest_workers[queue_name] = asyncio.create_task(
                work_ingest_queue(queue, queue_name=queue_name)
            )
        for task_meta, cur_task in queue.all_tasks():
            if not cur_task.done():
                continue
            logger.info("worker task failed", kind=task_meta.kind)
            # task failed. record result and restart
            exception = cur_task.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
            if task_meta.kind == "repo":
                queue.start_repo_worker(queue_name=task_meta.queue_name)
            elif task_meta.kind == "webhook":
                await queue.start_webhook_worker(queue_name=task_meta.queue_name)
            else:
                assert_never(task_meta.kind)
        if ingest_queue_watcher.done():
            logger.info("worker task failed", kind="ingest_queue_watcher")
            exception = ingest_queue_watcher.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
            ingest_queue_watcher = asyncio.create_task(
                ingest_queue_starter(ingest_workers, queue)
            )


if __name__ == "__main__":
    asyncio.run(main())
