from __future__ import annotations

import asyncio
from typing import AsyncIterator, Iterator, List, Optional, Tuple

import pytest
from pytest_mock import MockFixture

from kodiak.config import V1
from kodiak.events.base import Installation
from kodiak.events.push import Commit, Owner, PushEvent, Repository
from kodiak.pull_request import get_pr
from kodiak.push_filter import get_push_filter_config, save_push_filter_config
from kodiak.queries import (
    GetOpenPullRequestsResponseSchema,
    HeadRef,
    PullRequestLabel,
    PullRequestUser,
    Ref,
)
from kodiak.queue import WebhookEvent, push
from kodiak.redis_client import redis_bot
from kodiak.test_pull_request import create_event
from kodiak.tests.fixtures import requires_redis

INSTALLATION_ID = "9234201"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """
    Share a loop between tests because the redis connection pool is bound to the
    loop it was first used on.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class FakeQueue:
    def __init__(self) -> None:
        self.events: List[Tuple[int, bool]] = []

    async def enqueue(self, *, event: WebhookEvent, low_priority: bool = False) -> None:
        self.events.append((event.pull_request_number, low_priority))

    async def enqueue_for_repo(
        self, *, event: WebhookEvent, first: bool
    ) -> Optional[int]:
        raise NotImplementedError


class FakeClient:
    def __init__(self, open_pull_requests: List[GetOpenPullRequestsResponseSchema]):
        self.open_pull_requests = open_pull_requests

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_open_pull_requests(
        self, base: Optional[str] = None, head: Optional[str] = None
    ) -> List[GetOpenPullRequestsResponseSchema]:
        assert base == "main"
        return self.open_pull_requests


def open_pull_request(
    number: int, labels: List[str]
) -> GetOpenPullRequestsResponseSchema:
    return GetOpenPullRequestsResponseSchema(
        number=number,
        base=Ref(ref="main"),
        head=HeadRef(sha=f"sha-{number}"),
        labels=[PullRequestLabel(name=label) for label in labels],
        user=PullRequestUser(login="octocat"),
    )


def push_event(commits: Optional[List[Commit]] = None) -> PushEvent:
    return PushEvent(
        installation=Installation(id=int(INSTALLATION_ID)),
        ref="refs/heads/main",
        repository=Repository(name="api", owner=Owner(login="acme")),
        commits=commits or [],
    )


@pytest.fixture
async def repo_pull_requests(mocker: MockFixture) -> AsyncIterator[None]:
    # drop connections opened on other test modules' event loops
    await redis_bot.connection_pool.disconnect()
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient(
            [
                open_pull_request(1, labels=["automerge"]),
                open_pull_request(2, labels=["bug"]),
                open_pull_request(3, labels=[]),
            ]
        ),
    )
    yield
    await redis_bot.delete(f"kodiak:push_filter_config:{INSTALLATION_ID}.acme/api")


@requires_redis
async def test_push_only_queues_pull_requests_kodiak_may_act_on(
    repo_pull_requests: None,
) -> None:
    """
    Pull requests without the automerge label would only be evaluated to be
    ignored again, so a push to their base branch shouldn't queue them.
    """
    await save_push_filter_config(
        installation_id=INSTALLATION_ID, owner="acme", repo="api", config=V1(version=1)
    )
    queue = FakeQueue()

    await push(queue, push_event())

    assert queue.events == [(1, True)]


@requires_redis
async def test_push_without_cached_config_queues_all_pull_requests(
    repo_pull_requests: None,
) -> None:
    """
    Without a recent evaluation we don't know the config, so we evaluate
    everything as before.
    """
    queue = FakeQueue()

    await push(queue, push_event())

    assert queue.events == [(1, True), (2, True), (3, True)]


@requires_redis
async def test_push_changing_config_queues_all_pull_requests(
    repo_pull_requests: None,
) -> None:
    """
    The cached config may be stale after a push that changes it, so we evaluate
    everything and let the evaluations cache the new config.
    """
    await save_push_filter_config(
        installation_id=INSTALLATION_ID, owner="acme", repo="api", config=V1(version=1)
    )
    queue = FakeQueue()

    await push(queue, push_event(commits=[Commit(modified=[".github/.kodiak.toml"])]))

    assert queue.events == [(1, True), (2, True), (3, True)]
    assert (
        await get_push_filter_config(
            installation_id=INSTALLATION_ID, owner="acme", repo="api"
        )
        is None
    )


class FakeEventClient:
    async def __aenter__(self) -> FakeEventClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_event_info(self, pr_number: int) -> object:
        return create_event()


@requires_redis
async def test_get_pr_caches_push_filter_config(
    mocker: MockFixture, repo_pull_requests: None
) -> None:
    """
    Evaluating a pull request should cache the config pushes filter with.
    """
    mocker.patch("kodiak.pull_request.Client", return_value=FakeEventClient())

    async def noop(**kwargs: object) -> None:
        return None

    await get_pr(
        install=INSTALLATION_ID,
        owner="acme",
        repo="api",
        number=100,
        dequeue_callback=noop,
        requeue_callback=noop,
        queue_for_merge_callback=noop,
    )

    push_filter = await get_push_filter_config(
        installation_id=INSTALLATION_ID, owner="acme", repo="api"
    )
    assert push_filter is not None
    assert push_filter.merge.automerge_label == "automerge"
