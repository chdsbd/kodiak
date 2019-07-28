import json
from pathlib import Path
from typing import cast

import arrow
import pytest
from pytest_mock import MockFixture

from kodiak.config import V1, Merge, MergeMethod
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    Client,
    EventInfoResponse,
    GraphQLResponse,
    MergeableState,
    MergeStateStatus,
    Permission,
    PRReviewAuthor,
    PRReviewRequest,
    PRReviewState,
    PRReviewWithPermission,
    PullRequest,
    PullRequestState,
    RepoInfo,
    StatusContext,
    StatusState,
)
from kodiak.test_utils import wrap_future


@pytest.fixture
def private_key() -> str:
    return (
        Path(__file__).parent / "test" / "fixtures" / "github.voided.private-key.pem"
    ).read_text()


@pytest.mark.asyncio
async def test_get_default_branch_name_error(
    api_client: Client, mocker: MockFixture
) -> None:
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(dict(data=None, errors=[{"test": 123}])),
    )

    res = await api_client.get_default_branch_name()
    assert res is None


@pytest.fixture
def blocked_response() -> dict:
    return cast(
        dict,
        json.loads(
            (
                Path(__file__).parent
                / "test"
                / "fixtures"
                / "api"
                / "get_event"
                / "behind.json"
            ).read_text()
        ),
    )


@pytest.fixture
def block_event(config_file_expression: str, config_str: str) -> EventInfoResponse:
    config = V1(
        version=1, merge=Merge(automerge_label="automerge", method=MergeMethod.squash)
    )
    pr = PullRequest(
        id="e14ff7599399478fb9dbc2dacb87da72",
        number=100,
        mergeStateStatus=MergeStateStatus.BEHIND,
        state=PullRequestState.OPEN,
        mergeable=MergeableState.MERGEABLE,
        labels=["automerge"],
        latest_sha="8d728d017cac4f5ba37533debe65730abe65730a",
        baseRefName="master",
        headRefName="df825f90-9825-424c-a97e-733522027e4c",
        title="Update README.md",
        body="",
        bodyText="",
        bodyHTML="",
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
            "ci/circleci: backend_lint",
            "ci/circleci: backend_test",
            "ci/circleci: frontend_lint",
            "ci/circleci: frontend_test",
            "WIP (beta)",
        ],
        requiresStrictStatusChecks=True,
        requiresCommitSignatures=False,
    )

    return EventInfoResponse(
        config=config,
        config_str=config_str,
        config_file_expression=config_file_expression,
        head_exists=True,
        pull_request=pr,
        repo=rep_info,
        branch_protection=branch_protection,
        review_requests=[
            PRReviewRequest(name="ghost"),
            PRReviewRequest(name="ghost-team"),
            PRReviewRequest(name="ghost-mannequin"),
        ],
        reviews=[
            (
                PRReviewWithPermission(
                    createdAt=arrow.get("2019-05-22T15:29:34Z").datetime,
                    state=PRReviewState.COMMENTED,
                    username="ghost",
                    permission=Permission.WRITE,
                )
            ),
            (
                PRReviewWithPermission(
                    createdAt=arrow.get("2019-05-22T15:29:52Z").datetime,
                    state=PRReviewState.CHANGES_REQUESTED,
                    username="ghost",
                    permission=Permission.WRITE,
                )
            ),
            (
                PRReviewWithPermission(
                    createdAt=arrow.get("2019-05-22T15:30:52Z").datetime,
                    state=PRReviewState.COMMENTED,
                    username="kodiak",
                    permission=Permission.ADMIN,
                )
            ),
            (
                PRReviewWithPermission(
                    createdAt=arrow.get("2019-05-22T15:43:17Z").datetime,
                    state=PRReviewState.APPROVED,
                    username="ghost",
                    permission=Permission.WRITE,
                )
            ),
            (
                PRReviewWithPermission(
                    createdAt=arrow.get("2019-05-23T15:13:29Z").datetime,
                    state=PRReviewState.APPROVED,
                    username="walrus",
                    permission=Permission.WRITE,
                )
            ),
        ],
        status_contexts=[
            StatusContext(
                context="ci/circleci: backend_lint", state=StatusState.SUCCESS
            ),
            StatusContext(
                context="ci/circleci: backend_test", state=StatusState.SUCCESS
            ),
            StatusContext(
                context="ci/circleci: frontend_lint", state=StatusState.SUCCESS
            ),
            StatusContext(
                context="ci/circleci: frontend_test", state=StatusState.SUCCESS
            ),
        ],
        check_runs=[
            CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)
        ],
        valid_signature=True,
        valid_merge_methods=[MergeMethod.squash],
    )


# TODO: serialize EventInfoResponse to JSON to parametrize test
@pytest.mark.asyncio
async def test_get_event_info_blocked(
    api_client: Client,
    blocked_response: dict,
    block_event: EventInfoResponse,
    mocker: MockFixture,
) -> None:
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(
            GraphQLResponse(
                data=blocked_response.get("data"), errors=blocked_response.get("errors")
            )
        ),
    )

    res = await api_client.get_event_info(
        config_file_expression="master:.kodiak.toml", pr_number=100
    )
    assert res is not None
    assert res == block_event
