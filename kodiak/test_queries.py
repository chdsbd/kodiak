import json
import typing
from pathlib import Path

import arrow
import pytest

from kodiak.config import V1, Merge, MergeMethod
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    Client,
    CommentAuthorAssociation,
    EventInfoResponse,
    GraphQLResponse,
    MergableState,
    MergeStateStatus,
    PRReview,
    PRReviewAuthor,
    PRReviewState,
    PullRequest,
    PullRequestState,
    RepoInfo,
    StatusContext,
    StatusState,
)


@pytest.fixture
def private_key() -> str:
    return (
        Path(__file__).parent / "test" / "fixtures" / "github.voided.private-key.pem"
    ).read_text()


@pytest.mark.asyncio
async def test_generate_jwt(private_key: str) -> None:
    async with Client(private_key=private_key, app_identifier="29196") as api:
        assert api.generate_jwt() is not None


@pytest.mark.asyncio
async def test_get_default_branch_name_error(mock_client: typing.Type[Client]) -> None:
    # TODO: Using patching instead of inheritance
    class MockClient(mock_client):  # type: ignore
        async def send_query(*args: typing.Any, **kwargs: typing.Any) -> dict:
            return dict(data=None, errors=[{"test": 123}])

    async with MockClient() as client:
        res = await client.get_default_branch_name(
            owner="recipeyak", repo="recipeyak", installation_id="23049845"
        )
        assert res is None


@pytest.fixture
def blocked_response() -> dict:
    return typing.cast(
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
def block_event() -> EventInfoResponse:
    config = V1(
        version=1, merge=Merge(whitelist=["automerge"], method=MergeMethod.squash)
    )
    pr = PullRequest(
        id="e14ff7599399478fb9dbc2dacb87da72",
        number=100,
        mergeStateStatus=MergeStateStatus.BEHIND,
        state=PullRequestState.OPEN,
        mergeable=MergableState.MERGEABLE,
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
        head_exists=True,
        pull_request=pr,
        repo=rep_info,
        branch_protection=branch_protection,
        review_requests_count=0,
        reviews=[
            PRReview(
                createdAt=arrow.get("2019-05-22T15:29:34Z").datetime,
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="ghost"),
                authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:29:52Z").datetime,
                state=PRReviewState.CHANGES_REQUESTED,
                author=PRReviewAuthor(login="ghost"),
                authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:30:52Z").datetime,
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="kodiak"),
                authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:43:17Z").datetime,
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="ghost"),
                authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
            ),
            PRReview(
                createdAt=arrow.get("2019-05-23T15:13:29Z").datetime,
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="walrus"),
                authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
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
    mock_client: typing.Type[Client],
    blocked_response: dict,
    block_event: EventInfoResponse,
) -> None:
    # mypy doesn't handle this circular type
    class MockClient(mock_client):  # type: ignore
        async def send_query(
            self,
            query: str,
            variables: typing.Mapping[str, typing.Union[str, int, None]],
            installation_id: typing.Optional[str] = None,
            remaining_retries: int = 4,
        ) -> GraphQLResponse:
            return GraphQLResponse(
                data=blocked_response.get("data"), errors=blocked_response.get("errors")
            )

    async with MockClient() as client:
        res = await client.get_event_info(
            owner="recipeyak",
            repo="recipeyak",
            config_file_expression="master:.kodiak.toml",
            pr_number=100,
            installation_id="928788A24C8C",
        )
        assert res is not None
        assert res == block_event
