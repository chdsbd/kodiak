import pytest
import asyncio

from starlette.testclient import TestClient

from kodiak import queries
from .main import app, RepoWorker, RepoQueue, PR, MergeabilityResponse, Retry


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
def pull_request():
    # the SHA of the most recent commit
    latest_sha: str
    baseRefName: str
    headRefName: str
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

        def get_default_branch_name(*args, **kwargs):
            return "master"

        def get_event_info(*args, **kwargs):
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
