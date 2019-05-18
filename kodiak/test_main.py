import pytest
import typing
import asyncio

from starlette.testclient import TestClient

from kodiak import queries
from kodiak.config import V1
from .main import (
    app,
    RepoWorker,
    RepoQueue,
    MergeResults,
    PR,
    MergeabilityResponse,
    Retry,
    _work_repo_queue,
    PREventData,
    RepoInfo,
)


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
@pytest.mark.asyncio
async def worker(gh_client):
    async def foo(queue: RepoQueue):
        pass

    q = RepoQueue()
    task = asyncio.create_task(foo(q))
    return RepoWorker(q=q, task=task, Client=gh_client)


@pytest.fixture
def create_pr():
    def create(mergeable_response: MergeabilityResponse):
        class FakePR(PR):
            async def mergability(self) -> MergeabilityResponse:
                return mergeable_response

        return FakePR(number=123, owner="tester", repo="repo", installation_id="abc")

    return create


MERGEABLE_RESPONSES = (
    MergeabilityResponse.OK,
    MergeabilityResponse.NEEDS_UPDATE,
    MergeabilityResponse.WAITING_FOR_CI,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mergeable_response", MERGEABLE_RESPONSES)
async def test_repo_worker_ingest_enqueable(
    create_pr, worker: RepoWorker, mergeable_response: MergeabilityResponse
):
    pr = create_pr(mergeable_response)

    res = await worker.ingest(pr)

    assert res != Retry
    assert pr in worker.q.queue, "PR should be enqueued for future merge"


NOT_MERGEABLE_RESPONSES = (
    MergeabilityResponse.INTERNAL_PROBLEM,
    MergeabilityResponse.NOT_MERGABLE,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mergeable_response", NOT_MERGEABLE_RESPONSES)
async def test_repo_worker_ingest_not_enqueable(
    create_pr, worker: RepoWorker, mergeable_response: MergeabilityResponse
):
    pr = create_pr(mergeable_response)

    res = await worker.ingest(pr)

    assert res != Retry
    assert pr not in worker.q.queue, "PR should not be enqueued"


@pytest.fixture
def config_file():
    return "version = 1\n"


@pytest.fixture
def config(config_file):
    return V1.parse_toml(config_file)


@pytest.fixture
def pull_request():
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
def repo():
    return queries.RepoInfo(
        merge_commit_allowed=False, rebase_merge_allowed=True, squash_merge_allowed=True
    )


@pytest.fixture
def event_response(config_file, pull_request, repo):
    return queries.EventInfoResponse(config_file, pull_request, repo)


@pytest.fixture
def gh_client(event_response: queries.EventInfoResponse):
    class MockClient(queries.Client):
        def __init__(
            self,
            token=None,
            private_key=None,
            private_key_path=None,
            app_identifier=None,
        ):
            return super().__init__(
                token="abc123",
                private_key=private_key,
                private_key_path=private_key_path,
                app_identifier=app_identifier,
            )

        async def send_query(*args, **kwargs):
            raise NotImplementedError

        async def get_default_branch_name(*args, **kwargs):
            return "master"

        async def get_event_info(*args, **kwargs):
            return event_response

        def generate_jwt(*args, **kwargs):
            return "abc"

        async def get_token_for_install(*args, **kwargs):
            return "abc"

    return MockClient


@pytest.mark.asyncio
async def test_repo_worker_ingest_need_refresh(gh_client, worker: RepoWorker):
    class FakePR(PR):
        async def mergability(self) -> MergeabilityResponse:
            return MergeabilityResponse.NEED_REFRESH

    pr = FakePR(
        number=123,
        owner="tester",
        repo="repo",
        installation_id="abc",
        Client=gh_client(),
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
        (MergeResults.WAITING, 1),
    ],
)
async def test_work_repo_queue(
    create_pr, merge_result: MergeResults, expected_length: int
):
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,result",
    [
        (
            queries.EventInfoResponse(config_file=None, pull_request=None, repo=None),
            None,
        ),
        (
            queries.EventInfoResponse(
                config_file="",
                pull_request=queries.PullRequest(
                    id="123",
                    mergeStateStatus=queries.MergeStateStatus.BEHIND,
                    state=queries.PullRequestState.OPEN,
                    mergeable=queries.MergableState.MERGEABLE,
                    labels=[],
                    latest_sha="abcd",
                    baseRefName="some-branch",
                    headRefName="another-branch",
                ),
                repo=queries.RepoInfo(False, False, False),
            ),
            None,
        ),
    ],
)
async def test_pr_get_event_failures(gh_client, response, result):
    class MyMockClient(gh_client):  # type: ignore
        async def get_event_info(*args, **kwargs):
            return response

    pr = PR(
        number=123,
        owner="tester",
        repo="repo",
        installation_id="abc",
        Client=MyMockClient,
    )
    res = await pr.get_event()
    assert res == result


@pytest.fixture
def pr(gh_client):
    return PR(
        number=123, owner="tester", repo="repo", installation_id="abc", Client=gh_client
    )


@pytest.mark.asyncio
async def test_pr_get_event_success(gh_client, pull_request, pr, config):
    res = await pr.get_event()
    assert res == PREventData(
        pull_request=pull_request, config=config, repo_info=RepoInfo(False, True, True)
    )
