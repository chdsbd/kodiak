from __future__ import annotations

from typing import List, Optional

from pytest_mock import MockFixture

from kodiak.events.base import Installation
from kodiak.events.status import Owner, Repository, StatusEvent
from kodiak.queries import GetOpenPullRequestsResponseSchema, HeadRef, Ref
from kodiak.queue import WebhookEvent, status_event


class FakeQueue:
    def __init__(self) -> None:
        self.events: List[WebhookEvent] = []

    async def enqueue(self, *, event: WebhookEvent) -> None:
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
        assert base is None and head is None
        return self.open_pull_requests


def open_pull_request(number: int, sha: str) -> GetOpenPullRequestsResponseSchema:
    return GetOpenPullRequestsResponseSchema(
        number=number, base=Ref(ref="main"), head=HeadRef(sha=sha)
    )


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
