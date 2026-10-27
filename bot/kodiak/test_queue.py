import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import AsyncIterator, Iterator, List, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from pytest_mock import MockFixture

from kodiak.entrypoints.worker import work_ingest_queue
from kodiak.errors import InstallationTokenError
from kodiak.queue import (
    MERGE_QUEUE_NAMES,
    WEBHOOK_QUEUE_NAMES,
    RedisWebhookQueue,
    WebhookEvent,
    get_ingest_queue,
    get_merge_queue_name,
    get_webhook_queue_name,
    installation_id_from_queue,
    process_repo_queue,
)
from kodiak.redis_client import redis_bot
from kodiak.schemas import RawWebhookEvent
from kodiak.tests.fixtures import RecordingLogger, requires_redis


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


@pytest.fixture
async def merge_queues() -> AsyncIterator[Tuple[str, str]]:
    queue_name = get_merge_queue_name(webhook_event)
    empty_queue_name = queue_name + "-empty"
    yield queue_name, empty_queue_name
    await redis_bot.srem(MERGE_QUEUE_NAMES, queue_name, empty_queue_name)
    await redis_bot.delete(
        queue_name, empty_queue_name, f"merge_queue_by_install:{INSTALLATION_ID}"
    )


@requires_redis
async def test_create_restarts_merge_queue_workers(
    mocker: MockFixture, merge_queues: Tuple[str, str]
) -> None:
    """
    On restart we should start a worker for each merge queue with events and
    forget merge queues that are empty.
    """
    queue_name, empty_queue_name = merge_queues
    before_restart = RedisWebhookQueue()
    mocker.patch.object(before_restart, "start_repo_worker")
    await before_restart.enqueue_for_repo(event=webhook_event, first=False)
    await redis_bot.sadd(MERGE_QUEUE_NAMES, empty_queue_name)

    after_restart = RedisWebhookQueue()
    start_repo_worker = mocker.patch.object(after_restart, "start_repo_worker")
    await after_restart.create()

    start_repo_worker.assert_called_once_with(queue_name=queue_name)
    assert await redis_bot.smembers(MERGE_QUEUE_NAMES) >= {queue_name.encode()}
    assert not await redis_bot.sismember(MERGE_QUEUE_NAMES, empty_queue_name)


@pytest.fixture
async def webhook_queue(mocker: MockFixture) -> AsyncIterator[RedisWebhookQueue]:
    queue = RedisWebhookQueue()
    mocker.patch.object(queue, "start_webhook_worker")
    yield queue
    queue_name = get_webhook_queue_name(webhook_event)
    await redis_bot.srem(WEBHOOK_QUEUE_NAMES, queue_name)
    await redis_bot.delete(queue_name)


async def queued_pull_request_numbers() -> List[int]:
    events = await redis_bot.zrange(get_webhook_queue_name(webhook_event), 0, -1)
    return [WebhookEvent.parse_raw(event).pull_request_number for event in events]


@requires_redis
async def test_enqueue_direct_event_skips_low_priority_backlog(
    webhook_queue: RedisWebhookQueue,
) -> None:
    """
    An event for a pull request's own activity should be handled before
    earlier fan-out events, like those from a push to the base branch.
    """
    for number in (1, 2):
        await webhook_queue.enqueue(
            event=webhook_event.copy(update=dict(pull_request_number=number)),
            low_priority=True,
        )
    await webhook_queue.enqueue(
        event=webhook_event.copy(update=dict(pull_request_number=3))
    )

    assert await queued_pull_request_numbers() == [3, 1, 2]


@requires_redis
async def test_enqueue_direct_event_moves_queued_low_priority_event_ahead(
    webhook_queue: RedisWebhookQueue,
) -> None:
    """
    If a pull request is already queued at low priority, an event for its own
    activity should move it ahead instead of leaving it at the back.
    """
    pr_1 = webhook_event.copy(update=dict(pull_request_number=1))
    pr_2 = webhook_event.copy(update=dict(pull_request_number=2))
    await webhook_queue.enqueue(event=pr_1, low_priority=True)
    await webhook_queue.enqueue(event=pr_2, low_priority=True)

    await webhook_queue.enqueue(event=pr_2)

    assert await queued_pull_request_numbers() == [2, 1]


@requires_redis
async def test_enqueue_low_priority_event_keeps_queued_position(
    webhook_queue: RedisWebhookQueue,
) -> None:
    """
    A fan-out event for a pull request that's already queued shouldn't push it
    to the back.
    """
    pr_1 = webhook_event.copy(update=dict(pull_request_number=1))
    pr_2 = webhook_event.copy(update=dict(pull_request_number=2))
    await webhook_queue.enqueue(event=pr_1)
    await webhook_queue.enqueue(event=pr_2)

    await webhook_queue.enqueue(event=pr_1, low_priority=True)

    assert await queued_pull_request_numbers() == [1, 2]


@requires_redis
async def test_work_ingest_queue_logs_lagging_events(
    mocker: MockFixture, redis_queue: str
) -> None:
    """
    We should log events that waited a long time in the ingest queue, so we can
    tell when ingest falls behind, but not events handled promptly.
    """
    mocker.patch(
        "kodiak.entrypoints.worker.handle_webhook_event", new_callable=AsyncMock
    )
    ingest_queue = get_ingest_queue(INSTALLATION_ID)
    lagging_event = RawWebhookEvent(
        event_name="status", payload={}, received_at=time.time() - 120
    ).json()
    prompt_event = RawWebhookEvent(
        event_name="push", payload={}, received_at=time.time()
    ).json()
    await redis_bot.rpush(ingest_queue, lagging_event, prompt_event)
    logger = RecordingLogger()
    mocker.patch("kodiak.entrypoints.worker.logger", logger)
    worker = asyncio.create_task(
        work_ingest_queue(RedisWebhookQueue(), queue_name=ingest_queue)
    )

    async def two_events_handled() -> None:
        while len(logger.events("ingest_event_handled")) < 2:
            await asyncio.sleep(0.01)

    await asyncio.wait_for(two_events_handled(), timeout=5)
    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker

    (lagging_log,) = logger.events("ingest_event_lagging")
    assert lagging_log["event_name"] == "status"
    assert lagging_log["lag_sec"] >= 120
    assert lagging_log["queue_length"] == 1
