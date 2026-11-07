from __future__ import annotations

from typing import AsyncIterator, List, Optional

import pytest
from pytest_mock import MockFixture

from kodiak.config import V1
from kodiak.events.base import Installation
from kodiak.events.pull_request import (
    Commit as PullRequestCommit,
    Owner as PullRequestOwner,
    PullRequest,
    PullRequestEvent,
    Ref as PullRequestRef,
    Repository as PullRequestRepository,
)
from kodiak.events.status import Branch, Commit, Owner, Repository, StatusEvent
from kodiak.push_filter import (
    get_cache_key,
    save_pull_request_ignored,
    save_push_filter_config,
)
from kodiak.queries import (
    CommitPullRequestSchema,
    GetOpenPullRequestsResponseSchema,
    HeadRef,
    PullRequestLabel,
    PullRequestUser,
    Ref,
)
from kodiak.queue import WebhookEvent, pr_event, status_event
from kodiak.redis_client import create_connection
from kodiak.tests.fixtures import RecordingLogger, requires_redis


@pytest.fixture(autouse=True)
async def push_filter_redis(mocker: MockFixture) -> AsyncIterator[None]:
    # use our own client because the shared one may hold connections from other
    # tests' event loops.
    redis = create_connection()
    mocker.patch("kodiak.push_filter.redis_bot", redis)
    yield
    await redis.delete(
        get_cache_key(installation_id="9234201", owner="acme", repo="api"),
        *await redis.keys("kodiak:status_commit_pull_requests:9234201.acme/api:*"),
        *await redis.keys("kodiak:ignored_pull_request:9234201.acme/api#*"),
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
    def __init__(
        self,
        *,
        commit_pull_requests: List[CommitPullRequestSchema],
        open_pull_requests: List[GetOpenPullRequestsResponseSchema],
    ):
        self.commit_pull_requests = commit_pull_requests
        self.open_pull_requests = open_pull_requests
        self.listed_open_pull_requests = False
        self.commit_lookups = 0
        self.open_pull_request_lookups = 0

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_pull_requests_for_commit(
        self, sha: str
    ) -> List[CommitPullRequestSchema]:
        self.commit_lookups += 1
        return self.commit_pull_requests

    async def get_open_pull_requests(
        self, base: Optional[str] = None, head: Optional[str] = None
    ) -> List[GetOpenPullRequestsResponseSchema]:
        assert base is None
        self.open_pull_request_lookups += 1
        if head is not None:
            return [
                pr for pr in self.open_pull_requests if f"acme:{pr.head.sha}" == head
            ]
        self.listed_open_pull_requests = True
        return self.open_pull_requests


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


@requires_redis
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


@requires_redis
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


@requires_redis
async def test_status_event_for_unmatched_commit_looks_up_once(
    mocker: MockFixture,
) -> None:
    """
    A build reports dozens of statuses for a commit after its pull request
    merges. Once we know no open pull request is at the commit, the rest of
    its statuses shouldn't spend API calls finding that out again.
    """
    client = FakeClient(
        commit_pull_requests=[commit_pull_request(124, sha="f3b02e4", state="closed")],
        open_pull_requests=[],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, status_without_branches(sha="f3b02e4"))
    await status_event(queue, status_without_branches(sha="f3b02e4"))

    assert client.commit_lookups == 1
    assert queue.events == []


@requires_redis
async def test_status_event_for_pull_request_commit_looks_up_once(
    mocker: MockFixture,
) -> None:
    """
    Each status for a pull request's head commit can change its mergeability,
    so we queue the pull request for every status, but only look it up once.
    """
    client = FakeClient(
        commit_pull_requests=[commit_pull_request(124, sha="f3b02e4", state="open")],
        open_pull_requests=[],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, status_without_branches(sha="f3b02e4"))
    await status_event(queue, status_without_branches(sha="f3b02e4"))

    assert client.commit_lookups == 1
    assert queue.events == [queued(124), queued(124)]


@requires_redis
async def test_status_event_for_branch_commit_looks_up_once(
    mocker: MockFixture,
) -> None:
    """
    A build reports dozens of statuses for a pull request's head commit. Only
    the first should spend an API call finding its pull request.
    """
    client = FakeClient(
        commit_pull_requests=[],
        open_pull_requests=[open_pull_request(124, sha="f3b02e4")],
    )
    mocker.patch("kodiak.queue.Client", return_value=client)
    queue = FakeQueue()

    await status_event(queue, branch_status_event("f3b02e4"))
    await status_event(queue, branch_status_event("f3b02e4"))

    assert client.open_pull_request_lookups == 1
    assert queue.events == [queued(124), queued(124)]


@requires_redis
async def test_repeat_status_event_skips_ignored_pull_request(
    mocker: MockFixture,
) -> None:
    """
    We don't remember a pull request's labels with its commit, so repeat
    statuses skip the pull requests evaluation found Kodiak can't act on.
    """
    mocker.patch(
        "kodiak.queue.Client",
        return_value=FakeClient(
            commit_pull_requests=[],
            open_pull_requests=[open_pull_request(124, sha="f3b02e4")],
        ),
    )
    await status_event(FakeQueue(), branch_status_event("f3b02e4"))
    await save_pull_request_ignored(
        installation_id="9234201", owner="acme", repo="api", number=124, ignored=True
    )
    queue = FakeQueue()

    await status_event(queue, branch_status_event("f3b02e4"))

    assert queue.events == []


@requires_redis
async def test_pull_request_event_forgets_its_commit(mocker: MockFixture) -> None:
    """
    A pull request opened at a commit we found no pull request at should be
    evaluated for the commit's next status.
    """
    client = FakeClient(commit_pull_requests=[], open_pull_requests=[])
    mocker.patch("kodiak.queue.Client", return_value=client)
    await status_event(FakeQueue(), branch_status_event("f3b02e4"))
    client.open_pull_requests = [open_pull_request(124, sha="f3b02e4")]
    await pr_event(
        FakeQueue(),
        PullRequestEvent(
            installation=Installation(id=9234201),
            number=124,
            pull_request=PullRequest(
                base=PullRequestRef(ref="main"),
                head=PullRequestCommit(sha="f3b02e4"),
            ),
            repository=PullRequestRepository(
                name="api", owner=PullRequestOwner(login="acme")
            ),
        ),
    )
    queue = FakeQueue()

    await status_event(queue, branch_status_event("f3b02e4"))

    assert queue.events == [queued(124)]


@requires_redis
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


@requires_redis
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
            commit_pull_requests=[],
            open_pull_requests=[
                open_pull_request(123, sha="1d7a5c9", labels=["automerge"]),
                open_pull_request(124, sha="f3b02e4"),
            ],
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
        return_value=FakeClient(
            commit_pull_requests=[],
            open_pull_requests=[open_pull_request(124, sha="f3b02e4")],
        ),
    )
    queue = FakeQueue()

    await status_event(queue, branch_status_event("f3b02e4"))

    assert [event.pull_request_number for event in queue.events] == [124]
