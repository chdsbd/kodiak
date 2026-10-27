import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import AsyncIterator, Iterator, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from pytest_mock import MockFixture

from kodiak import queue as queue_module
from kodiak.entrypoints.worker import webhook_queue_starter, work_ingest_queue
from kodiak.errors import InstallationTokenError
from kodiak.queue import (
    MERGE_QUEUE_NAMES,
    QUEUE_PUBSUB_WEBHOOK,
    WEBHOOK_QUEUE_NAMES,
    RedisWebhookQueue,
    WebhookEvent,
    get_ingest_queue,
    get_merge_queue_name,
    get_webhook_queue_name,
    installation_id_from_queue,
    process_repo_queue,
    push_webhook_event,
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
        ("webhook:11256551.acme/api.example.com", "11256551"),
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

    await process_repo_queue(structlog.get_logger(), redis_queue, RedisWebhookQueue())

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


def test_get_webhook_queue_name_per_repo() -> None:
    """
    Each repository gets its own webhook queue so a backlog in one repository
    doesn't delay events for other repositories in the installation.
    """
    other_repo_event = webhook_event.copy(update=dict(repo_name="web"))

    assert get_webhook_queue_name(webhook_event) == "webhook:9234201.acme/api"
    assert get_webhook_queue_name(other_repo_event) == "webhook:9234201.acme/web"


@pytest.fixture
async def webhook_queue() -> AsyncIterator[str]:
    queue_name = get_webhook_queue_name(webhook_event)
    yield queue_name
    await redis_bot.srem(WEBHOOK_QUEUE_NAMES, queue_name)
    await redis_bot.delete(queue_name)


@requires_redis
async def test_push_webhook_event_registers_queue(webhook_queue: str) -> None:
    """
    Events queued outside the worker process must be recorded in
    WEBHOOK_QUEUE_NAMES so the worker can find them.
    """
    assert await push_webhook_event(webhook_event) == webhook_queue

    assert await redis_bot.sismember(WEBHOOK_QUEUE_NAMES, webhook_queue)
    assert await redis_bot.zrange(webhook_queue, 0, -1) == [
        webhook_event.json().encode()
    ]


@requires_redis
async def test_webhook_queue_starter_starts_published_queue(
    mocker: MockFixture,
) -> None:
    """
    Other processes publish webhook queue names to ask the worker process to
    start a worker for them.
    """
    queue = RedisWebhookQueue()
    start_webhook_worker = mocker.patch.object(queue, "start_webhook_worker")
    watcher = asyncio.create_task(webhook_queue_starter(queue))

    async def publish_until_started() -> None:
        while not start_webhook_worker.called:
            await redis_bot.publish(QUEUE_PUBSUB_WEBHOOK, "webhook:9234201")
            await asyncio.sleep(0.01)

    await asyncio.wait_for(publish_until_started(), timeout=5)

    start_webhook_worker.assert_called_with(queue_name="webhook:9234201")
    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher


@pytest.fixture
def idle_immediately(mocker: MockFixture) -> None:
    mocker.patch("kodiak.queue.conf.WEBHOOK_WORKER_IDLE_TIMEOUT_SEC", 0)
    mocker.patch("kodiak.queue.conf.REDIS_BLOCKING_POP_TIMEOUT_SEC", 1)


@requires_redis
async def test_idle_webhook_worker_exits(
    idle_immediately: None, webhook_queue: str
) -> None:
    """
    A webhook worker with an empty queue should exit and forget its queue so we
    don't hold a Redis connection for every repository we've ever seen.
    """
    await redis_bot.sadd(WEBHOOK_QUEUE_NAMES, webhook_queue)
    queue = RedisWebhookQueue()

    queue.start_webhook_worker(queue_name=webhook_queue)
    worker, _kind = queue.worker_tasks[webhook_queue]
    await asyncio.wait_for(worker, timeout=5)

    assert not await redis_bot.sismember(WEBHOOK_QUEUE_NAMES, webhook_queue)


@requires_redis
async def test_idle_webhook_worker_handles_event_queued_while_exiting(
    mocker: MockFixture, idle_immediately: None, webhook_queue: str
) -> None:
    """
    An event queued while the worker is forgetting its queue must still be
    processed, even though starting the still-running worker is a no-op.
    """
    evaluate_pr = mocker.patch("kodiak.queue.evaluate_pr", new_callable=AsyncMock)
    queue = RedisWebhookQueue()
    forget_webhook_queue_if_empty = queue_module.forget_webhook_queue_if_empty

    async def forget_then_enqueue(queue_name: str) -> bool:
        forgotten = await forget_webhook_queue_if_empty(queue_name)
        if not evaluate_pr.called:
            await queue.enqueue(event=webhook_event)
        return forgotten

    mocker.patch(
        "kodiak.queue.forget_webhook_queue_if_empty", side_effect=forget_then_enqueue
    )
    await redis_bot.sadd(WEBHOOK_QUEUE_NAMES, webhook_queue)

    queue.start_webhook_worker(queue_name=webhook_queue)
    worker, _kind = queue.worker_tasks[webhook_queue]
    await asyncio.wait_for(worker, timeout=10)

    assert evaluate_pr.call_count == 1
    assert await redis_bot.zcard(webhook_queue) == 0
    assert not await redis_bot.sismember(WEBHOOK_QUEUE_NAMES, webhook_queue)
