from datetime import datetime
from typing import Union

import pydantic
import pytest
import toml
from pytest_mock import MockFixture
from starlette.testclient import TestClient

from kodiak import queries
from kodiak.config import V1
from kodiak.main import app
from kodiak.queries import Client


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
def config(
    config_file: str
) -> Union[V1, pydantic.ValidationError, toml.TomlDecodeError]:
    return V1.parse_toml(config_file)


@pytest.fixture
def pull_request() -> queries.PullRequest:
    return queries.PullRequest(
        id="MDExOlB1bGxSZXF1ZXN0MjgxODQ0Nzg2",
        number=235,
        mergeStateStatus=queries.MergeStateStatus.BEHIND,
        state=queries.PullRequestState.OPEN,
        mergeable=queries.MergeableState.MERGEABLE,
        labels=[],
        latest_sha="abcd",
        baseRefName="some-branch",
        headRefName="another-branch",
        title="adding blah",
        body="# hello world",
        bodyText="hello world",
        bodyHTML="<h1>hello world</h1>",
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
        requiresCommitSignatures=False,
    )


@pytest.fixture
def review() -> queries.PRReview:
    return queries.PRReview(
        state=queries.PRReviewState.APPROVED,
        createdAt=datetime(2015, 5, 25),
        author=queries.PRReviewAuthor(
            login="ghost", permission=queries.Permission.WRITE
        ),
    )


@pytest.fixture
def review_request() -> queries.PRReviewRequest:
    return queries.PRReviewRequest(name="ghost")


@pytest.fixture
def status_context() -> queries.StatusContext:
    return queries.StatusContext(context="ci/api", state=queries.StatusState.SUCCESS)


@pytest.fixture
def context(status_context: queries.StatusContext) -> queries.StatusContext:
    return status_context


@pytest.fixture
def config_file_expression() -> str:
    return "master:.kodiak.toml"


@pytest.fixture
def config_str() -> str:
    return """\
version = 1
[merge]
method = "squash"
"""


@pytest.fixture
def event_response(
    config_str: str,
    config_file_expression: str,
    pull_request: queries.PullRequest,
    repo: queries.RepoInfo,
    branch_protection: queries.BranchProtectionRule,
    review: queries.PRReview,
    status_context: queries.StatusContext,
    config: V1,
) -> queries.EventInfoResponse:
    return queries.EventInfoResponse(
        config_str=config_str,
        config_file_expression=config_file_expression,
        config=config,
        pull_request=pull_request,
        repo=repo,
        branch_protection=branch_protection,
        head_exists=True,
        review_requests=[],
        reviews=[review],
        status_contexts=[status_context],
        valid_signature=True,
        valid_merge_methods=[queries.MergeMethod.merge],
    )


@pytest.fixture
def api_client(mocker: MockFixture) -> Client:
    client = Client(installation_id="foo", owner="foo", repo="foo")
    mocker.patch.object(client, "send_query")
    return client
