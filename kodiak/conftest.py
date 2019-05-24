import typing
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kodiak import queries
from kodiak.config import V1
from kodiak.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def configure_structlog() -> None:
    """
    Configures cleanly structlog for each test method.
    https://github.com/hynek/structlog/issues/76#issuecomment-240373958
    """
    import structlog

    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.KeyValueRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
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
        title="adding blah",
        bodyText="hello world",
    )


@pytest.fixture
def repo() -> queries.RepoInfo:
    return queries.RepoInfo(
        merge_commit_allowed=False, rebase_merge_allowed=True, squash_merge_allowed=True
    )


@pytest.fixture
def branch_protection() -> queries.BranchProtectionRule:
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
def mock_client(
    event_response: queries.EventInfoResponse
) -> typing.Type[queries.Client]:
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

    return MockClient
