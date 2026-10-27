from __future__ import annotations

from typing import List, Optional

from pytest_mock import MockFixture

from kodiak.events.base import Installation
from kodiak.events.status import Owner, Repository, StatusEvent
from kodiak.queries import (
    CommitPullRequestSchema,
    GetOpenPullRequestsResponseSchema,
    HeadRef,
    Ref,
)
from kodiak.queue import WebhookEvent, status_event
from kodiak.tests.fixtures import RecordingLogger


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
    def __init__(
        self,
        *,
        commit_pull_requests: List[CommitPullRequestSchema],
        open_pull_requests: List[GetOpenPullRequestsResponseSchema],
    ):
        self.commit_pull_requests = commit_pull_requests
        self.open_pull_requests = open_pull_requests
        self.listed_open_pull_requests = False

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_pull_requests_for_commit(
        self, sha: str
    ) -> List[CommitPullRequestSchema]:
        return self.commit_pull_requests

    async def get_open_pull_requests(
        self, base: Optional[str] = None, head: Optional[str] = None
    ) -> List[GetOpenPullRequestsResponseSchema]:
        assert base is None and head is None
        self.listed_open_pull_requests = True
        return self.open_pull_requests


def open_pull_request(number: int, sha: str) -> GetOpenPullRequestsResponseSchema:
    return GetOpenPullRequestsResponseSchema(
        number=number, base=Ref(ref="main"), head=HeadRef(sha=sha)
    )


def commit_pull_request(number: int, sha: str, state: str) -> CommitPullRequestSchema:
    return CommitPullRequestSchema(
        number=number, base=Ref(ref="main"), head=HeadRef(sha=sha), state=state
    )


def status_without_branches(sha: str) -> StatusEvent:
    return StatusEvent(
        installation=Installation(id=9234201),
        id=4523,
        sha=sha,
        branches=[],
        repository=Repository(name="api", owner=Owner(login="acme")),
    )


def queued(number: int) -> WebhookEvent:
    return WebhookEvent(
        repo_owner="acme",
        repo_name="api",
        pull_request_number=number,
        target_name="main",
        installation_id="9234201",
    )


async def test_status_event_without_branches_queues_pull_request_at_commit(
    mocker: MockFixture,
) -> None:
    """
    When no branch has the status commit at its head, we look up the pull
    requests containing that commit and only queue the open one whose head is
    at it, without listing every open pull request.
    """
    client = FakeClient(
        commit_pull_requests=[
            commit_pull_request(123, sha="1d7a5c9", state="open"),
            commit_pull_request(124, sha="f3b02e4", state="open"),
        ],
        open_pull_requests=[],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, status_without_branches(sha="f3b02e4"))

    assert queue.events == [queued(124)]
    assert client.listed_open_pull_requests is False


async def test_status_event_for_merged_pull_request_queues_nothing(
    mocker: MockFixture,
) -> None:
    """
    A build still running when its pull request merges keeps reporting statuses
    after the branch is deleted. The only pull request with that commit is
    closed, so there is nothing to evaluate.
    """
    client = FakeClient(
        commit_pull_requests=[commit_pull_request(124, sha="f3b02e4", state="closed")],
        open_pull_requests=[open_pull_request(125, sha="8c41b6a")],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, status_without_branches(sha="f3b02e4"))

    assert queue.events == []
    assert client.listed_open_pull_requests is False


async def test_status_event_for_fork_pull_request_lists_open_pull_requests(
    mocker: MockFixture,
) -> None:
    """
    GitHub doesn't associate commits from forks with their pull request, so when
    it finds no pull request we search the open pull requests for the one at
    that commit.
    """
    client = FakeClient(
        commit_pull_requests=[],
        open_pull_requests=[
            open_pull_request(123, sha="1d7a5c9"),
            open_pull_request(124, sha="f3b02e4"),
        ],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, status_without_branches(sha="f3b02e4"))

    assert queue.events == [queued(124)]


async def test_status_event_without_branches_logs_why(mocker: MockFixture) -> None:
    """
    The log says which pull requests GitHub associates with the commit, so we
    can tell merged pull requests, moved branches and forks apart.
    """
    client = FakeClient(
        commit_pull_requests=[commit_pull_request(124, sha="f3b02e4", state="closed")],
        open_pull_requests=[],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    log = RecordingLogger()
    mocker.patch("kodiak.queue.logger", log)

    await status_event(FakeQueue(), status_without_branches(sha="f3b02e4"))

    [record] = log.events("could not find refs for status_event")
    assert record["sha"] == "f3b02e4"
    assert record["commit_pull_requests"] == ["124:closed"]
    assert record["listed_open_pull_requests"] is False
    assert record["matching_pull_requests"] == []
