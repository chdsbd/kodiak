from __future__ import annotations

from typing import AsyncIterator, List, Optional

import pytest
from pytest_mock import MockFixture

from kodiak.config import V1
from kodiak.events.base import Installation
from kodiak.events.status import Branch, Commit, Owner, Repository, StatusEvent
from kodiak.push_filter import get_cache_key, save_push_filter_config
from kodiak.queries import (
    GetOpenPullRequestsResponseSchema,
    HeadRef,
    PullRequestLabel,
    PullRequestUser,
    Ref,
)
from kodiak.queue import WebhookEvent, status_event
from kodiak.redis_client import create_connection
from kodiak.tests.fixtures import requires_redis


@pytest.fixture(autouse=True)
async def push_filter_redis(mocker: MockFixture) -> AsyncIterator[None]:
    # use our own client because the shared one may hold connections from other
    # tests' event loops.
    redis = create_connection()
    mocker.patch("kodiak.push_filter.redis_bot", redis)
    yield
    await redis.delete(
        get_cache_key(installation_id="9234201", owner="acme", repo="api")
    )
    await redis.close()


class FakeQueue:
    def __init__(self) -> None:
        self.events: List[WebhookEvent] = []

    async def enqueue(self, *, event: WebhookEvent, low_priority: bool = False) -> None:
        self.events.append(event)

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
        assert base is None
        if head is None:
            return self.open_pull_requests
        return [pr for pr in self.open_pull_requests if f"acme:{pr.head.sha}" == head]


def open_pull_request(
    number: int, sha: str, labels: Optional[List[str]] = None
) -> GetOpenPullRequestsResponseSchema:
    return GetOpenPullRequestsResponseSchema(
        number=number,
        base=Ref(ref="main"),
        head=HeadRef(sha=sha),
        labels=[PullRequestLabel(name=label) for label in labels or []],
        user=PullRequestUser(login="octocat"),
    )


@requires_redis
async def test_status_event_without_branches_only_queues_matching_pull_request(
    mocker: MockFixture,
) -> None:
    """
    When no branch has the status commit at its head, we search the open pull
    requests for the one at that commit instead of queueing all of them.
    """
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient(
            [
                open_pull_request(123, sha="1d7a5c9"),
                open_pull_request(124, sha="f3b02e4"),
                open_pull_request(125, sha="8c41b6a"),
            ]
        ),
    )
    queue = FakeQueue()
    event = StatusEvent(
        installation=Installation(id=9234201),
        id=4523,
        sha="f3b02e4",
        branches=[],
        repository=Repository(name="api", owner=Owner(login="acme")),
    )

    await status_event(queue, event)

    assert queue.events == [
        WebhookEvent(
            repo_owner="acme",
            repo_name="api",
            pull_request_number=124,
            target_name="main",
            installation_id="9234201",
        )
    ]


@requires_redis
async def test_status_event_for_merged_pull_request_queues_nothing(
    mocker: MockFixture,
) -> None:
    """
    A build still running when its pull request merges keeps reporting statuses
    after the branch is deleted. No open pull request has that commit, so there
    is nothing to evaluate.
    """
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient(
            [
                open_pull_request(123, sha="1d7a5c9"),
                open_pull_request(125, sha="8c41b6a"),
            ]
        ),
    )
    queue = FakeQueue()
    event = StatusEvent(
        installation=Installation(id=9234201),
        id=4523,
        sha="f3b02e4",
        branches=[],
        repository=Repository(name="api", owner=Owner(login="acme")),
    )

    await status_event(queue, event)

    assert queue.events == []


def branch_status_event(*branch_names: str) -> StatusEvent:
    """
    A status for a commit at the head of each named branch. Our fake client
    names branches after their head commit.
    """
    return StatusEvent(
        installation=Installation(id=9234201),
        id=4523,
        sha=branch_names[0],
        branches=[
            Branch(name=name, commit=Commit(sha=branch_names[0]))
            for name in branch_names
        ],
        repository=Repository(name="api", owner=Owner(login="acme")),
    )


@requires_redis
async def test_status_event_skips_pull_requests_kodiak_wont_act_on(
    mocker: MockFixture,
) -> None:
    """
    A status can't change anything for a pull request Kodiak ignores, so we
    shouldn't evaluate pull requests without the automerge label.
    """
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient(
            [
                open_pull_request(123, sha="1d7a5c9", labels=["automerge"]),
                open_pull_request(124, sha="f3b02e4"),
            ]
        ),
    )
    await save_push_filter_config(
        installation_id="9234201", owner="acme", repo="api", config=V1(version=1)
    )
    labeled, unlabeled = FakeQueue(), FakeQueue()

    await status_event(labeled, branch_status_event("1d7a5c9"))
    await status_event(unlabeled, branch_status_event("f3b02e4"))

    assert [event.pull_request_number for event in labeled.events] == [123]
    assert unlabeled.events == []


@requires_redis
async def test_status_event_without_cached_config_queues_pull_request(
    mocker: MockFixture,
) -> None:
    """
    Without a recent evaluation we don't know the config, so we evaluate the
    pull request as before.
    """
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient([open_pull_request(124, sha="f3b02e4")]),
    )
    queue = FakeQueue()

    await status_event(queue, branch_status_event("f3b02e4"))

    assert [event.pull_request_number for event in queue.events] == [124]
