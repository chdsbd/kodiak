from __future__ import annotations

import json
from typing import TYPE_CHECKING, AsyncIterator

import pytest
from pytest_mock import MockFixture

from kodiak import queue as queue_module
from kodiak.queue import (
    MERGE_QUEUE_NAMES,
    WEBHOOK_QUEUE_NAMES,
    RedisWebhookQueue,
    WebhookEvent,
    get_ingest_queue,
    get_processing_queue_name,
    installation_id_from_queue,
    process_ingest_event,
    process_repo_queue,
    process_webhook_event,
    recover_ingest_queue,
    recover_processing_zset,
)
from kodiak.redis_client import create_connection
from kodiak.schemas import RawWebhookEvent
from kodiak.tests.fixtures import requires_redis

if TYPE_CHECKING:
    from redis.asyncio import Redis


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


INSTALL_ID = 424242
INSTALL_ID_STR = str(INSTALL_ID)


@pytest.fixture
async def redis(mocker: MockFixture) -> AsyncIterator[Redis[bytes]]:
    """
    A Redis connection created on the test's event loop, patched into the
    queue module. Keys are scoped to INSTALL_ID and cleared after each test.
    """
    conn = create_connection()
    mocker.patch.object(queue_module, "redis_bot", conn)

    async def clear() -> None:
        keys = set()
        for pattern in (
            f"*{INSTALL_ID}*",
            "kodiak_merge_queue_names:v2",
            "kodiak_webhook_queue_names",
        ):
            keys.update(await conn.keys(pattern))
        if keys:
            await conn.delete(*keys)

    await clear()
    yield conn
    await clear()
    await conn.close()


def make_event(number: int) -> WebhookEvent:
    return WebhookEvent(
        repo_owner="acme",
        repo_name="app",
        pull_request_number=number,
        installation_id=INSTALL_ID_STR,
        target_name="main",
    )


def raw_event(event_name: str = "ping") -> str:
    return RawWebhookEvent(
        event_name=event_name, payload={"installation": {"id": INSTALL_ID}}
    ).json()


class FakeQueue:
    async def enqueue(self, *, event: WebhookEvent) -> None: ...

    async def enqueue_for_repo(self, *, event: WebhookEvent, first: bool) -> int | None:
        return None


@requires_redis
async def test_process_ingest_event_holds_event_while_processing(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    While an ingest event is being handled it should live in the processing
    list so it can be recovered if we crash. Once handled it should be removed.
    """
    queue_name = get_ingest_queue(INSTALL_ID)
    processing = get_processing_queue_name(queue_name)
    event = raw_event()
    await redis.lpush(queue_name, event)

    seen_in_processing = []

    async def fake_handle(**kwargs: object) -> None:
        seen_in_processing.append(await redis.lrange(processing, 0, -1))

    mocker.patch.object(queue_module, "handle_webhook_event", fake_handle)
    await process_ingest_event(FakeQueue(), queue_name, queue_module.logger)

    assert seen_in_processing == [[event.encode()]]
    assert await redis.llen(queue_name) == 0
    assert await redis.llen(processing) == 0


@requires_redis
async def test_process_ingest_event_removes_event_on_exception(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    An exception from the handler should not leave the event stuck in the
    processing list.
    """
    queue_name = get_ingest_queue(INSTALL_ID)
    await redis.lpush(queue_name, raw_event())

    async def fake_handle(**kwargs: object) -> None:
        raise ValueError("boom")

    mocker.patch.object(queue_module, "handle_webhook_event", fake_handle)
    with pytest.raises(ValueError):
        await process_ingest_event(FakeQueue(), queue_name, queue_module.logger)

    assert await redis.llen(get_processing_queue_name(queue_name)) == 0


@requires_redis
async def test_process_ingest_event_oldest_first(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    Ingest pushes to the head of the list, so the worker must pop from the
    tail to process events in the order they arrived.
    """
    queue_name = get_ingest_queue(INSTALL_ID)
    for name in ("first", "second", "third"):
        await redis.lpush(queue_name, raw_event(name))

    handled = []

    async def fake_handle(**kwargs: object) -> None:
        handled.append(kwargs["event_name"])

    mocker.patch.object(queue_module, "handle_webhook_event", fake_handle)
    for _ in range(3):
        await process_ingest_event(FakeQueue(), queue_name, queue_module.logger)

    assert handled == ["first", "second", "third"]


@requires_redis
async def test_recover_ingest_queue(redis: Redis[bytes]) -> None:
    """
    Events left in the processing list from a crash should be placed back on
    the queue ahead of newer events.
    """
    queue_name = get_ingest_queue(INSTALL_ID)
    processing = get_processing_queue_name(queue_name)
    await redis.lpush(queue_name, raw_event("newer"))
    # brpoplpush pushes to the head of the processing list, so "older" was
    # taken first and is at the tail.
    await redis.lpush(processing, raw_event("older"))
    await redis.lpush(processing, raw_event("old"))

    assert await recover_ingest_queue(queue_name) == 2

    # the worker pops from the tail, so the tail should be the oldest event.
    order = [
        json.loads(v)["event_name"]
        for v in reversed(await redis.lrange(queue_name, 0, -1))
    ]
    assert order == ["older", "old", "newer"]
    assert await redis.exists(processing) == 0

    assert await recover_ingest_queue(queue_name) == 0


@requires_redis
async def test_process_webhook_event_holds_event_while_evaluating(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    A webhook event should sit in the processing set during evaluation and
    be removed afterwards. The main queue must be free for new events for the
    same pull request while we evaluate.
    """
    event = make_event(1)
    queue_name = event.get_webhook_queue_name()
    processing = get_processing_queue_name(queue_name)
    await redis.zadd(queue_name, {event.json(): 5.0})

    during = []

    async def fake_evaluate_pr(**kwargs: object) -> None:
        during.append(
            (
                await redis.zrange(processing, 0, -1, withscores=True),
                await redis.zcard(queue_name),
            )
        )

    mocker.patch.object(queue_module, "evaluate_pr", fake_evaluate_pr)
    await process_webhook_event(RedisWebhookQueue(), queue_name, queue_module.logger)

    assert during == [([(event.json().encode(), 5.0)], 0)]
    assert await redis.zcard(processing) == 0
    assert await redis.zcard(queue_name) == 0


@requires_redis
async def test_recover_processing_zset(redis: Redis[bytes]) -> None:
    """
    Events left in a processing set should be merged back into the queue,
    keeping the earliest position if the event is in both.
    """
    queue_name = make_event(1).get_webhook_queue_name()
    processing = get_processing_queue_name(queue_name)
    stuck = make_event(1).json()
    waiting = make_event(2).json()
    await redis.zadd(queue_name, {stuck: 10.0, waiting: 8.0})
    await redis.zadd(processing, {stuck: 3.0})

    await recover_processing_zset(queue_name)

    assert await redis.zrange(queue_name, 0, -1, withscores=True) == [
        (stuck.encode(), 3.0),
        (waiting.encode(), 8.0),
    ]
    assert await redis.exists(processing) == 0

    # recovering with nothing in processing is a no-op.
    await recover_processing_zset(queue_name)
    assert await redis.zcard(queue_name) == 2


@requires_redis
async def test_process_repo_queue_keeps_pull_request_until_done(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    The pull request being merged should stay at the head of the merge queue
    with its original score until merging finishes, so a crash doesn't drop
    it or lose its position.
    """
    merging = make_event(1)
    waiting = make_event(2)
    queue_name = merging.get_merge_queue_name()
    await redis.zadd(queue_name, {merging.json(): 5.0, waiting.json(): 9.0})

    during = []

    async def fake_evaluate_pr(**kwargs: object) -> None:
        during.append(
            (
                await redis.zrange(queue_name, 0, -1, withscores=True),
                await redis.get(merging.get_merge_target_queue_name()),
            )
        )

    mocker.patch.object(queue_module, "evaluate_pr", fake_evaluate_pr)
    await process_repo_queue(queue_module.logger, queue_name)

    assert during == [
        (
            [(merging.json().encode(), 5.0), (waiting.json().encode(), 9.0)],
            merging.json().encode(),
        )
    ]
    assert await redis.zrange(queue_name, 0, -1) == [waiting.json().encode()]
    assert await redis.exists(merging.get_merge_target_queue_name()) == 0
    assert await redis.exists(merging.get_merge_target_queue_name() + ":time") == 0


@requires_redis
async def test_process_repo_queue_cleans_up_on_exception(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    merging = make_event(1)
    queue_name = merging.get_merge_queue_name()
    await redis.zadd(queue_name, {merging.json(): 5.0})

    async def fake_evaluate_pr(**kwargs: object) -> None:
        raise ValueError("boom")

    mocker.patch.object(queue_module, "evaluate_pr", fake_evaluate_pr)
    with pytest.raises(ValueError):
        await process_repo_queue(queue_module.logger, queue_name)

    assert await redis.zcard(queue_name) == 0
    assert await redis.exists(merging.get_merge_target_queue_name()) == 0


@requires_redis
async def test_enqueue_for_repo_registers_queue_name(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    Merge queue names must be recorded so workers can be restarted for them.
    """
    mocker.patch.object(RedisWebhookQueue, "start_repo_worker")
    event = make_event(1)
    position = await RedisWebhookQueue().enqueue_for_repo(event=event, first=False)
    assert position == 0
    assert await redis.sismember(MERGE_QUEUE_NAMES, event.get_merge_queue_name())


@requires_redis
async def test_create_restarts_workers(
    redis: Redis[bytes], mocker: MockFixture
) -> None:
    """
    On startup we should restart workers for merge queues that still have
    pull requests waiting, forget empty ones, and recover any webhook events
    that were mid-evaluation.
    """
    waiting = make_event(1)
    busy_queue = waiting.get_merge_queue_name()
    empty_queue = f"merge_queue:{INSTALL_ID}.acme/other/main"
    await redis.sadd(MERGE_QUEUE_NAMES, busy_queue, empty_queue)
    await redis.zadd(busy_queue, {waiting.json(): 1.0})

    webhook_queue = waiting.get_webhook_queue_name()
    await redis.sadd(WEBHOOK_QUEUE_NAMES, webhook_queue)
    await redis.zadd(
        get_processing_queue_name(webhook_queue), {make_event(3).json(): 2.0}
    )

    started_repo = mocker.patch.object(RedisWebhookQueue, "start_repo_worker")
    started_webhook = mocker.patch.object(RedisWebhookQueue, "start_webhook_worker")

    await RedisWebhookQueue().create()

    started_repo.assert_called_once_with(queue_name=busy_queue)
    started_webhook.assert_called_once_with(queue_name=webhook_queue)
    assert await redis.smembers(MERGE_QUEUE_NAMES) == {busy_queue.encode()}
    assert await redis.zrange(webhook_queue, 0, -1) == [make_event(3).json().encode()]
