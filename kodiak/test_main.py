import pytest
import asyncio

from starlette.testclient import TestClient

from .main import app, RepoWorker, RepoQueue, PR, MergeabilityResponse, Retry


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
@pytest.mark.asyncio
async def worker():
    async def foo(queue: RepoQueue):
        pass

    q = RepoQueue()
    task = asyncio.create_task(foo(q))
    return RepoWorker(q=q, task=task)


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


@pytest.mark.skip("need to mock out Client")
@pytest.mark.asyncio
async def test_repo_worker_ingest_need_refresh(mocker, create_pr, worker: RepoWorker):
    patched = mocker.patch("kodiak.main.Client.get_token_for_install")
    fut: "asyncio.Future[str]" = asyncio.Future()
    fut.set_result("123")
    patched.return_value = fut
    pr = create_pr(MergeabilityResponse.NEED_REFRESH)

    res = await worker.ingest(pr)

    assert res == Retry
    assert pr not in worker.q.queue, "PR should not be enqueued"
