import asyncio
import typing
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kodiak import queries
from kodiak.config import V1

from .main import (
    PR,
    MergeabilityResponse,
    MergeResults,
    RepoQueue,
    RepoWorker,
    Retry,
    _work_repo_queue,
)


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
@pytest.mark.asyncio
async def worker(gh_client: typing.Type[queries.Client]) -> RepoWorker:
    async def foo(queue: RepoQueue) -> None:
        pass

    q = RepoQueue()
    task = asyncio.create_task(foo(q))
    return RepoWorker(q=q, task=task, Client=gh_client)


@pytest.fixture
def create_pr() -> typing.Callable:
    def create(mergeable_response: MergeabilityResponse) -> PR:
        class FakePR(PR):
            async def mergability(self) -> typing.Tuple[MergeabilityResponse, V1]:
                return mergeable_response, V1(version=1)

        return FakePR(number=123, owner="tester", repo="repo", installation_id="abc")

    return create


MERGEABLE_RESPONSES = (
    MergeabilityResponse.OK,
    MergeabilityResponse.NEEDS_UPDATE,
    MergeabilityResponse.NEED_REFRESH,
    MergeabilityResponse.WAIT,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mergeable_response", MERGEABLE_RESPONSES)
async def test_repo_worker_ingest_enqueable(
    create_pr: typing.Callable,
    worker: RepoWorker,
    mergeable_response: MergeabilityResponse,
) -> None:
    pr = create_pr(mergeable_response)

    res = await worker.ingest(pr)

    assert res != Retry
    assert pr in worker.q.queue, "PR should be enqueued for future merge"


NOT_MERGEABLE_RESPONSES = (MergeabilityResponse.NOT_MERGEABLE,)


@pytest.mark.asyncio
@pytest.mark.parametrize("mergeable_response", NOT_MERGEABLE_RESPONSES)
async def test_repo_worker_ingest_not_enqueable(
    create_pr: typing.Callable,
    worker: RepoWorker,
    mergeable_response: MergeabilityResponse,
) -> None:
    worker.q.queue.clear()
    pr = create_pr(mergeable_response)

    res = await worker.ingest(pr)

    assert res != Retry
    assert pr not in worker.q.queue, "PR should not be enqueued"


def test_mergeability_response_coverage() -> None:
    assert len(MergeabilityResponse) == len(
        MERGEABLE_RESPONSES + NOT_MERGEABLE_RESPONSES
    )


@pytest.fixture
def config_file() -> str:
    return "version = 1\n"


@pytest.fixture
def config(config_file: str) -> V1:
    return V1.parse_toml(config_file)


@pytest.fixture
def pull_request() -> queries.PullRequest:
    return queries.PullRequest(
        id="123",
        mergeStateStatus=queries.MergeStateStatus.BEHIND,
        state=queries.PullRequestState.OPEN,
        mergeable=queries.MergableState.MERGEABLE,
        labels=[],
        latest_sha="abcd",
        baseRefName="some-branch",
        headRefName="another-branch",
    )


@pytest.fixture
def repo() -> queries.RepoInfo:
    return queries.RepoInfo(
        merge_commit_allowed=False, rebase_merge_allowed=True, squash_merge_allowed=True
    )


@pytest.fixture
def branch_protection() -> queries.BranchProtectionRule:

    requiredApprovingReviewCount: typing.Optional[int]
    requiresStatusChecks: bool
    requiredStatusCheckContexts: typing.List[str]
    requiresStrictStatusChecks: bool
    requiresCommitSignatures: bool

    return queries.BranchProtectionRule(
        requiresApprovingReviews=True,
        requiredApprovingReviewCount=2,
        requiresStatusChecks=True,
        requiredStatusCheckContexts=["ci/example"],
        requiresStrictStatusChecks=True,
        requiresCommitSignatures=True,
    )


@pytest.fixture
def review() -> queries.PRReview:
    return queries.PRReview(id="abc", state=queries.PRReviewState.APPROVED)


@pytest.fixture
def status_context() -> queries.StatusContext:
    return queries.StatusContext(context="123", state=queries.StatusState.SUCCESS)


@pytest.fixture
def event_response(
    config_file: str,
    pull_request: queries.PullRequest,
    repo: queries.RepoInfo,
    branch_protection: queries.BranchProtectionRule,
    review: queries.PRReview,
    status_context: queries.StatusContext,
) -> queries.EventInfoResponse:
    return queries.EventInfoResponse(
        config,
        pull_request,
        repo,
        branch_protection,
        review_requests_count=0,
        reviews=[review],
        status_contexts=[status_context],
        valid_signature=True,
        valid_merge_methods=[queries.MergeMethod.merge],
    )


@pytest.fixture
def gh_client(event_response: queries.EventInfoResponse) -> typing.Type[queries.Client]:
    class MockClient(queries.Client):
        def __init__(
            self,
            token: typing.Optional[str] = None,
            private_key: typing.Optional[str] = None,
            private_key_path: typing.Optional[Path] = None,
            app_identifier: typing.Optional[str] = None,
        ) -> None:
            super().__init__(
                token="abc123",
                private_key=private_key,
                private_key_path=private_key_path,
                app_identifier=app_identifier,
            )

        async def send_query(*args: typing.Any, **kwargs: typing.Any) -> None:
            raise NotImplementedError

        async def get_default_branch_name(
            *args: typing.Any, **kwargs: typing.Any
        ) -> str:
            return "master"

        async def get_event_info(
            *args: typing.Any, **kwargs: typing.Any
        ) -> queries.EventInfoResponse:
            return event_response

        def generate_jwt(*args: typing.Any, **kwargs: typing.Any) -> str:
            return "abc"

        async def get_token_for_install(*args: typing.Any, **kwargs: typing.Any) -> str:
            return "abc"

    return MockClient


@pytest.mark.asyncio
async def test_repo_worker_ingest_need_refresh(
    gh_client: typing.Type[queries.Client], worker: RepoWorker
) -> None:
    worker.q.queue.clear()

    class FakePR(PR):
        async def mergability(self) -> typing.Tuple[MergeabilityResponse, V1]:
            return MergeabilityResponse.NEED_REFRESH, V1(version=1)

    pr = FakePR(
        number=123, owner="tester", repo="repo", installation_id="abc", Client=gh_client
    )

    res = await worker.ingest(pr)

    assert isinstance(res, Retry)
    assert pr not in worker.q.queue, "PR should not be enqueued"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "merge_result,expected_length",
    [
        (MergeResults.OK, 0),
        (MergeResults.CANNOT_MERGE, 0),
        (MergeResults.API_FAILURE, 1),
    ],
)
async def test_work_repo_queue(
    monkeypatch: typing.Any,
    create_pr: typing.Callable,
    merge_result: MergeResults,
    expected_length: int,
) -> None:
    # don't wait during tests
    import kodiak

    monkeypatch.setattr(kodiak.main, "MERGE_SLEEP_SECONDS", 0)

    class FakePR(PR):
        async def merge(self) -> MergeResults:
            return merge_result

    pr = FakePR(number=123, owner="tester", repo="repo", installation_id="abc")
    q = RepoQueue()
    # HACK: pytest doesn't cleanup between parametrized test runs
    q.queue.clear()
    q.queue.append(pr)
    await _work_repo_queue(q)
    assert len(q.queue) == expected_length


def test_pr(gh_client: typing.Type[queries.Client]) -> None:
    a = PR(
        number=123,
        owner="ghost",
        repo="ghost",
        installation_id="abc123",
        Client=gh_client,
    )
    b = PR(number=123, owner="ghost", repo="ghost", installation_id="abc123")
    assert a == b, "equality should work even though they have different clients"

    from collections import deque

    assert a in deque([b])
