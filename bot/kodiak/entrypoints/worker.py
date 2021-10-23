"""
Process webhook events from the Redis queues.
"""
from __future__ import annotations

import asyncio
from typing import NoReturn

import asyncio_redis
import sentry_sdk
import structlog

from kodiak import app_config as conf
from kodiak.assertions import assert_never
from kodiak.logging import configure_logging
from kodiak.queue import (
    QUEUE_INGEST,
    RedisWebhookQueue,
    WebhookQueueProtocol,
    handle_webhook_event,
)
from kodiak.schemas import RawWebhookEvent

configure_logging()

logger = structlog.get_logger()


async def work_ingest_queue(queue: WebhookQueueProtocol) -> NoReturn:
    redis = await asyncio_redis.Connection.create(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=(
            conf.REDIS_URL.password.encode() if conf.REDIS_URL.password else None
        ),
        ssl=conf.REDIS_URL.scheme == "rediss",
    )

    while True:
        raw_event = await redis.blpop([QUEUE_INGEST])
        parsed_event = RawWebhookEvent.parse_raw(raw_event.value)
        await handle_webhook_event(
            queue=queue,
            event_name=parsed_event.event_name,
            payload=parsed_event.payload,
        )


async def main() -> NoReturn:
    queue = RedisWebhookQueue()
    await queue.create()

    tasks = [
        asyncio.create_task(work_ingest_queue(queue))
        for _ in range(conf.QUEUE_WORKER_COUNT)
    ]

    while True:
        # Health check the various tasks and recreate them if necessary.
        # There's probably a cleaner way to do this.
        await asyncio.sleep(0.25)
        for idx, worker_task in enumerate(tasks):
            if not worker_task.done():
                continue
            logger.info("task failed")
            # task failed. record result and restart
            exception = worker_task.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
            tasks[idx] = asyncio.create_task(work_ingest_queue(queue))
        for task_meta, cur_task in queue.all_tasks():
            if not cur_task.done():
                continue
            logger.info("task failed")
            # task failed. record result and restart
            exception = cur_task.exception()
            logger.info("exception", excep=exception)
            sentry_sdk.capture_exception(exception)
            if task_meta.kind == "repo":
                queue.start_repo_worker(queue_name=task_meta.queue_name)
            elif task_meta.kind == "webhook":
                queue.start_webhook_worker(queue_name=task_meta.queue_name)
            else:
                assert_never(task_meta.kind)


if __name__ == "__main__":
    asyncio.run(main())
