from typing import Any, Type, cast

import pytest
import requests

from kodiak.config import V1, Merge, MergeMethod
from kodiak.errors import ApiCallException
from kodiak.pull_request import PRV2, EventInfoResponse
from kodiak.queries import (
    BranchProtectionRule,
    Client,
    MergeableState,
    MergeStateStatus,
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
        repo=rep_info,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[],
        status_contexts=[],
        check_runs=[],
        valid_signature=True,
        valid_merge_methods=[MergeMethod.squash],
    )


@pytest.fixture
async def pr_v2() -> PRV2:
    async def dequeue() -> None:
        return None

    async def queue_for_merge() -> None:
        return None

    return PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=dequeue,
        queue_for_merge_callback=queue_for_merge,
    )


@pytest.mark.asyncio
async def test_pr_v2_merge() -> None:
    async def dequeue() -> None:
        return None

    async def queue_for_merge() -> None:
        return None

    class FakeClient:
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
            res = requests.Response()
            cast(
                Any, res
            )._content = b"""{
  "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
  "merged": true,
  "message": "Pull Request successfully merged"
}"""
            res.status_code = 200
            return res

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=dequeue,
        queue_for_merge_callback=queue_for_merge,
        client=cast(Type[Client], FakeClient),
    )
    await pr_v2.merge("squash", commit_title="", commit_message="")


@pytest.mark.asyncio
async def test_pr_v2_merge_rebase_error() -> None:
    async def dequeue() -> None:
        return None

    async def queue_for_merge() -> None:
        return None

    class FakeClient:
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
            res = requests.Response()
            cast(
                Any, res
            )._content = b"""{"message":"This branch can't be rebased","documentation_url":"https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button"}"""
            res.status_code = 405
            return res

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=dequeue,
        queue_for_merge_callback=queue_for_merge,
        client=cast(Type[Client], FakeClient),
    )
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge("squash", commit_title="", commit_message="")
    assert e.value.method == "merge pull request failed"
    assert e.value.description == "This branch can't be rebased"


@pytest.mark.asyncio
async def test_pr_v2_merge_service_unavailable() -> None:
    async def dequeue() -> None:
        return None

    async def queue_for_merge() -> None:
        return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            pass

        async def merge_pull_request(
            self,
            number: int,
            merge_method: object,
            commit_title: object,
            commit_message: object,
        ) -> requests.Response:
            res = requests.Response()
            cast(Any, res)._content = b"""<html>Service Unavailable</html>"""
            res.status_code = 503
            return res

    pr_v2 = PRV2(
        event=create_event(),
        install="88443234",
        owner="delos",
        repo="incite",
        number=8534,
        dequeue_callback=dequeue,
        queue_for_merge_callback=queue_for_merge,
        client=cast(Type[Client], FakeClient),
    )
    with pytest.raises(ApiCallException) as e:
        await pr_v2.merge("squash", commit_title="", commit_message="")
    assert e.value.method == "merge pull request failed"
    assert e.value.description is None
