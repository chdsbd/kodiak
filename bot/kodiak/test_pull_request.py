from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Type, cast

import httpx as requests
import pytest
from httpx import Request
from typing_extensions import Protocol

from kodiak.config import V1, Merge, MergeMethod
from kodiak.errors import ApiCallException
from kodiak.pull_request import PRV2, EventInfoResponse, QueueForMergeCallback
from kodiak.queries import (
    BranchProtectionRule,
    Client,
    MergeableState,
    MergeStateStatus,
    NodeListPushAllowance,
    PullRequest,
    PullRequestAuthor,
    PullRequestState,
    RepoInfo,
    ReviewThreadConnection,
)


def create_event() -> EventInfoResponse:
    config = V1(
        version=1, merge=Merge(automerge_label="automerge", method=MergeMethod.squash)
    )
    pr = PullRequest(
        id="e14ff7599399478fb9dbc2dacb87da72",
        number=100,
        author=PullRequestAuthor(login="arnold", databaseId=49118, type="Bot"),
        mergeStateStatus=MergeStateStatus.BEHIND,
        state=PullRequestState.OPEN,
        isDraft=False,
        mergeable=MergeableState.MERGEABLE,
        isCrossRepository=False,
        labels=["automerge"],
        latest_sha="8d728d017cac4f5ba37533debe65730abe65730a",
        baseRefName="master",
        headRefName="df825f90-9825-424c-a97e-733522027e4c",
        title="Update README.md",
        body="",
        bodyText="",
        bodyHTML="",
        url="https://github.com/delos-corp/hive-mind/pull/324",
        reviewThreads=ReviewThreadConnection(nodes=[], totalCount=0),
    )
    rep_info = RepoInfo(
        merge_commit_allowed=False,
        rebase_merge_allowed=False,
        squash_merge_allowed=True,
        is_private=True,
        delete_branch_on_merge=False,
    )
    branch_protection = BranchProtectionRule(
        requiresApprovingReviews=True,
        requiredApprovingReviewCount=2,
        requiresStatusChecks=True,
        requiredStatusCheckContexts=[
            "ci/circleci: frontend_lint",
            "ci/circleci: frontend_test",
        ],
        requiresStrictStatusChecks=True,
        requiresCodeOwnerReviews=False,
        requiresCommitSignatures=False,
        requiresConversationResolution=False,
        restrictsPushes=False,
        pushAllowances=NodeListPushAllowance(nodes=[]),
    )

    return EventInfoResponse(
        config=config,
        config_str="""\
version = 1
[merge]
method = "squash"
""",
        config_file_expression="master:.kodiak.toml",
        head_exists=True,
        pull_request=pr,
        repository=rep_info,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[],
        status_contexts=[],
        check_runs=[],
        valid_merge_methods=[MergeMethod.squash],
        subscription=None,
    )


async def noop(*args: object, **kwargs: object) -> None:
    return None


class BaseMockFunc:
    calls: List[Mapping[str, Any]]

    def __init__(self) -> None:
        self.calls = []

    def log_call(self, args: Dict[str, Any]) -> None:
        self.calls.append(args)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def called(self) -> bool:
        return self.call_count > 0

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: id={id(self)} call_count={self.call_count!r} called={self.called!r} calls={self.calls!r}>"


class MockMergePullRequest(BaseMockFunc):
    response: requests.Response

    async def __call__(
        self, number: int, merge_method: str, commit_title: str, commit_message: str
    ) -> requests.Response:
        self.log_call(
            dict(
                number=number,
                merge_method=merge_method,
                commit_title=commit_title,
                commit_message=commit_message,
            )
        )
        return self.response


class MockDeleteLabel(BaseMockFunc):
    response: requests.Response

    async def __call__(self, label: str, pull_number: int) -> requests.Response:
        self.log_call(dict(label=label, pull_number=pull_number))
        return self.response


class MockAddLabel(BaseMockFunc):
    response: requests.Response

    async def __call__(self, label: str, pull_number: int) -> requests.Response:
        self.log_call(dict(label=label, pull_number=pull_number))
        return self.response


class MockUpdateBranch(BaseMockFunc):
    response: requests.Response

    async def __call__(self, pull_number: int) -> requests.Response:
        self.log_call(dict(pull_number=pull_number))
        return self.response


class MockUpdateRef(BaseMockFunc):
    response: requests.Response

    async def __call__(self, *, ref: str, sha: str) -> requests.Response:
        self.log_call(dict(ref=ref, sha=sha))
        return self.response


class FakeClientProtocol(Protocol):
    merge_pull_request: MockMergePullRequest
    delete_label: MockDeleteLabel
    add_label: MockAddLabel
    update_branch: MockUpdateBranch
    update_ref: MockUpdateRef

    def __init__(self, *args: object, **kwargs: object) -> None:
        ...

    async def __aenter__(self) -> FakeClientProtocol:
        ...

    async def __aexit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        ...


def create_client() -> Type[FakeClientProtocol]:
    class FakeClient:
        merge_pull_request = MockMergePullRequest()
        delete_label = MockDeleteLabel()
        add_label = MockAddLabel()
        update_branch = MockUpdateBranch()
        update_ref = MockUpdateRef()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            pass

    return FakeClient


def create_response(content: bytes, status_code: int) -> requests.Response:
    return requests.Response(
        status_code=status_code, content=content, request=Request(method="", url="")
    )


def create_prv2(
    event: Optional[EventInfoResponse] = None,
    install: str = "88443234",
    owner: str = "delos",
    repo: str = "incite",
    number: int = 8634,
    dequeue_callback: Callable[[], Awaitable[None]] = noop,
    queue_for_merge_callback: QueueForMergeCallback = noop,
    requeue_callback: Callable[[], Awaitable[None]] = noop,
    client: Optional[Type[FakeClientProtocol]] = None,
) -> PRV2:
    return PRV2(
        event=event if event is not None else create_event(),
        install=install,
        owner=owner,
        repo=repo,
        number=number,
        dequeue_callback=dequeue_callback,
        queue_for_merge_callback=queue_for_merge_callback,
        requeue_callback=requeue_callback,
        client=cast(Type[Client], client if client is not None else create_client()),
    )


@pytest.mark.asyncio
async def test_pr_v2_merge() -> None:
    """
    We should be able to merge successfully
    """
    client = create_client()
    client.merge_pull_request.response = create_response(
        content=b"""{
      "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
      "merged": true,
      "message": "Pull Request successfully merged"
    }""",
        status_code=200,
    )

    pr_v2 = create_prv2(client=client)
    await pr_v2.merge("squash", commit_title="my title", commit_message="my message")
    assert client.merge_pull_request.call_count == 1


@pytest.mark.asyncio
async def test_pr_v2_merge_rebase_error() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.merge_pull_request.response = create_response(
        content=b"""{"message":"This branch can't be rebased","documentation_url":"https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button"}""",
        status_code=405,
    )

    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge(
            "squash", commit_title="my title", commit_message="my message"
        )
    assert client.merge_pull_request.call_count == 1
    assert e.value.method == "pull_request/merge"
    assert e.value.status_code == 405
    assert b"merge-a-pull-request-merge-button" in e.value.response


@pytest.mark.asyncio
async def test_pr_v2_merge_service_unavailable() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.merge_pull_request.response = create_response(
        content=b"""<html>Service Unavailable</html>""", status_code=503
    )

    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge(
            "squash", commit_title="my title", commit_message="my message"
        )
    assert client.merge_pull_request.call_count == 1
    assert e.value.method == "pull_request/merge"
    assert e.value.status_code == 503
    assert b"Service Unavailable" in e.value.response


@pytest.mark.asyncio
async def test_pr_v2_update_branch_ok() -> None:
    """
    We should be able to update a branch.
    """
    client = create_client()
    client.update_branch.response = create_response(content=b"", status_code=204)
    pr_v2 = create_prv2(client=client)
    await pr_v2.update_branch()
    assert client.update_branch.call_count == 1
    assert client.update_branch.calls[0]["pull_number"] == pr_v2.number


@pytest.mark.asyncio
async def test_pr_v2_update_branch_service_unavailable() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.update_branch.response = create_response(
        content=b"<html>Service Unavailable</html>", status_code=503
    )
    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.update_branch()
    assert client.update_branch.call_count == 1
    assert client.update_branch.calls[0]["pull_number"] == pr_v2.number
    assert e.value.method == "pull_request/update_branch"
    assert e.value.status_code == 503
    assert b"Service Unavailable" in e.value.response


@pytest.mark.asyncio
async def test_pr_v2_add_label_ok() -> None:
    """
    We should be able to add a label.
    """
    client = create_client()
    client.add_label.response = create_response(content=b"", status_code=204)
    pr_v2 = create_prv2(client=client)
    await pr_v2.add_label(label="some-label-to-delete")
    assert client.add_label.call_count == 1
    assert client.add_label.calls[0]["label"] == "some-label-to-delete"


@pytest.mark.asyncio
async def test_pr_v2_add_label_service_unavailable() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.add_label.response = create_response(
        content=b"<html>Service Unavailable</html>", status_code=503
    )
    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.add_label(label="some-label-to-delete")
    assert client.add_label.call_count == 1
    assert client.add_label.calls[0]["label"] == "some-label-to-delete"
    assert e.value.method == "pull_request/add_label"
    assert e.value.status_code == 503
    assert b"Service Unavailable" in e.value.response


@pytest.mark.asyncio
async def test_pr_v2_remove_label_ok() -> None:
    """
    Check that remove_label works when 
    """
    client = create_client()
    client.delete_label.response = create_response(content=b"", status_code=204)
    pr_v2 = create_prv2(client=client)
    await pr_v2.remove_label(label="some-label-to-delete")
    assert client.delete_label.call_count == 1
    assert client.delete_label.calls[0]["label"] == "some-label-to-delete"


@pytest.mark.asyncio
async def test_pr_v2_remove_label_service_unavailable() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.delete_label.response = create_response(
        content=b"<html>Service Unavailable</html>", status_code=503
    )
    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.remove_label(label="some-label-to-delete")
    assert client.delete_label.call_count == 1
    assert client.delete_label.calls[0]["label"] == "some-label-to-delete"
    assert e.value.method == "pull_request/delete_label"
    assert e.value.status_code == 503
    assert b"Service Unavailable" in e.value.response


@pytest.mark.asyncio
async def test_update_ref_ok() -> None:
    """
    Check that update_ref works 
    """
    client = create_client()
    client.update_ref.response = create_response(content=b"", status_code=200)
    pr_v2 = create_prv2(client=client)
    await pr_v2.update_ref(ref="master", sha="aa218f56b14c9653891f9e74264a383fa43fefbd")
    assert client.update_ref.call_count == 1
    assert client.update_ref.calls[0] == dict(
        ref="master", sha="aa218f56b14c9653891f9e74264a383fa43fefbd"
    )


@pytest.mark.asyncio
async def test_update_ref_service_unavailable() -> None:
    """
    We should raise ApiCallException when we get a bad API response.
    """
    client = create_client()
    client.update_ref.response = create_response(
        content=b"<html>Service Unavailable</html>", status_code=503
    )
    pr_v2 = create_prv2(client=client)
    with pytest.raises(ApiCallException) as e:
        await pr_v2.update_ref(
            ref="master", sha="aa218f56b14c9653891f9e74264a383fa43fefbd"
        )
    assert client.update_ref.call_count == 1
    assert client.update_ref.calls[0] == dict(
        ref="master", sha="aa218f56b14c9653891f9e74264a383fa43fefbd"
    )
    assert e.value.method == "pull_request/update_ref"
    assert e.value.status_code == 503
    assert b"Service Unavailable" in e.value.response
