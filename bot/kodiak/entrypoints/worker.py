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
from kodiak.queue import RedisWebhookQueue, WebhookQueueProtocol, handle_webhook_event
from kodiak.schemas import RawWebhookEvent

logger = structlog.get_logger()


async def work_ingest_queue(queue: WebhookQueueProtocol) -> NoReturn:
    redis = await asyncio_redis.Connection.create(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=(
            conf.REDIS_URL.password.encode() if conf.REDIS_URL.password else None
        ),
        encoder=asyncio_redis.encoders.BytesEncoder(),
        ssl=conf.REDIS_URL.scheme == "rediss",
    )

    while True:
        raw_event = await redis.blpop(["kodiak:ingest"])
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


if __name__ == "__main__":
    asyncio.run(main())
