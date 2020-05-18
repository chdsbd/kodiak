from __future__ import annotations
from typing import Any, Type, cast

import pytest
import requests
from typing_extensions import Protocol

from kodiak.config import V1, Merge, MergeMethod
from kodiak.errors import ApiCallException
from kodiak.pull_request import PRV2, EventInfoResponse
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
        requiresCommitSignatures=False,
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
        valid_signature=True,
        valid_merge_methods=[MergeMethod.squash],
        subscription=None,
    )


async def noop() -> None:
    return None


class FakeClientProtocol(Protocol):
    merge_pull_request_response: requests.Response

    def __init__(self, *args: object, **kwargs: object) -> None:
        ...

    async def __aenter__(self) -> FakeClientProtocol:
        ...

    async def __aexit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        ...

    async def merge_pull_request(
        self, number: int, merge_method: str, commit_title: str, commit_message: str
    ) -> requests.Response:
        ...


def create_client() -> Type[FakeClientProtocol]:
    class FakeClient:
        merge_pull_request_response: requests.Response = requests.Response()

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            pass

        async def merge_pull_request(
            self, number: int, merge_method: str, commit_title: str, commit_message: str
        ) -> requests.Response:
            return self.merge_pull_request_response

    return FakeClient


def create_response(content: bytes, status_code: int) -> requests.Response:
    res = requests.Response()
    cast(Any, res)._content = content
    res.status_code = status_code
    return res


@pytest.mark.asyncio
async def test_pr_v2_merge() -> None:
    client = create_client()
    client.merge_pull_request_response = create_response(
        content=b"""{
      "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
      "merged": true,
      "message": "Pull Request successfully merged"
    }""",
        status_code=200,
    )

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=noop,
        queue_for_merge_callback=noop,
        client=cast(Type[Client], client),
        requeue_callback=noop,
    )
    await pr_v2.merge("squash", commit_title="", commit_message="")


@pytest.mark.asyncio
async def test_pr_v2_merge_rebase_error() -> None:
    client = create_client()
    client.merge_pull_request_response = create_response(
        content=b"""{"message":"This branch can't be rebased","documentation_url":"https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button"}""",
        status_code=405,
    )

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=noop,
        queue_for_merge_callback=noop,
        client=cast(Type[Client], client),
        requeue_callback=noop,
    )
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge("squash", commit_title="", commit_message="")
    assert e.value.method == "merge"
    assert e.value.description == "This branch can't be rebased"


@pytest.mark.asyncio
async def test_pr_v2_merge_service_unavailable() -> None:
    client = create_client()
    client.merge_pull_request_response = create_response(
        content=b"""<html>Service Unavailable</html>""", status_code=503
    )

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=noop,
        queue_for_merge_callback=noop,
        client=cast(Type[Client], client),
        requeue_callback=noop,
    )
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge("squash", commit_title="", commit_message="")
    assert e.value.method == "merge"
    assert e.value.description is None
