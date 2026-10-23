import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import AsyncIterator, Iterator
from unittest.mock import MagicMock

import pytest
import structlog
from pytest_mock import MockFixture

from kodiak.entrypoints.worker import work_ingest_queue
from kodiak.errors import InstallationTokenError
from kodiak.queue import (
    RedisWebhookQueue,
    WebhookEvent,
    get_ingest_queue,
    installation_id_from_queue,
    process_repo_queue,
)
from kodiak.redis_client import redis_bot
from kodiak.schemas import RawWebhookEvent
from kodiak.tests.fixtures import requires_redis


@pytest.mark.parametrize(
    "queue_name, expected_installation_id",
    (
        ("merge_queue:11256551.sbdchd/squawk/main.test.foo", "11256551"),
        ("merge_queue:11256551.sbdchd/squawk", "11256551"),
        ("merge_queue:11256551.sbdchd/squawk:repo/main:test.branch", "11256551"),
        ("webhook:11256551", "11256551"),
        ("", ""),
    ),
)
def test_installation_id_from_queue(
    queue_name: str, expected_installation_id: str
) -> None:
    """
    We should gracefully parse an installation id from the queue name
    """
    assert installation_id_from_queue(queue_name) == expected_installation_id


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """
    Share a loop between tests because the redis connection pool is bound to the
    loop it was first used on.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


QUEUE_NAME = "kodiak:test_queue"
INSTALLATION_ID = 9234201


@pytest.fixture
def token_error(mocker: MockFixture) -> MagicMock:
    return mocker.patch(
        "kodiak.queries.get_token_for_install",
        side_effect=InstallationTokenError("IP allow list enabled"),
    )


@pytest.fixture
async def redis_queue() -> AsyncIterator[str]:
    yield QUEUE_NAME
    # cancelled blocking commands leave connections in a bad state
    await redis_bot.connection_pool.disconnect()
    await redis_bot.delete(QUEUE_NAME, get_ingest_queue(INSTALLATION_ID))
    await redis_bot.close()


webhook_event = WebhookEvent(
    repo_owner="acme",
    repo_name="api",
    pull_request_number=123,
    installation_id=str(INSTALLATION_ID),
    target_name="main",
)


@requires_redis
async def test_process_repo_queue_token_error(
    token_error: MagicMock, redis_queue: str
) -> None:
    """
    A failure to get an installation token should skip the event and clear the
    merge target instead of crashing the repo worker.
    """
    target_name = webhook_event.get_merge_target_queue_name()
    await redis_bot.zadd(redis_queue, {webhook_event.json(): time.time()})

    await process_repo_queue(structlog.get_logger(), redis_queue)

    assert token_error.call_count == 1
    assert await redis_bot.get(target_name) is None


@requires_redis
async def test_work_ingest_queue_token_error(
    token_error: MagicMock, redis_queue: str
) -> None:
    """
    A failure to get an installation token should skip the event and keep
    working the ingest queue.
    """
    payload = json.loads(
        (
            Path(__file__).parent / "test/fixtures/events/push/push_event.json"
        ).read_text()
    )
    payload["installation"]["id"] = INSTALLATION_ID
    payload["ref"] = "refs/heads/main"
    ingest_queue = get_ingest_queue(INSTALLATION_ID)
    event = RawWebhookEvent(event_name="push", payload=payload).json()
    await redis_bot.rpush(ingest_queue, event, event)

    worker = asyncio.create_task(
        work_ingest_queue(RedisWebhookQueue(), queue_name=ingest_queue)
    )

    async def two_events_handled() -> None:
        while token_error.call_count < 2 and not worker.done():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(two_events_handled(), timeout=5)

    assert not worker.done()
    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker
