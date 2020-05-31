import json
from pathlib import Path
from typing import Any, Dict, cast

import arrow
import asyncio_redis
import pytest
from pytest_mock import MockFixture
from requests_async import Response

from kodiak import app_config as conf
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
    NodeListPushAllowance,
    Permission,
    PRReview,
    PRReviewAuthor,
    PRReviewRequest,
    PRReviewState,
    PullRequest,
    PullRequestAuthor,
    PullRequestState,
    PushAllowance,
    PushAllowanceActor,
    RepoInfo,
    SeatsExceeded,
    StatusContext,
    StatusState,
    Subscription,
)
from kodiak.test_utils import wrap_future


@pytest.fixture
def private_key() -> str:
    return (
        Path(__file__).parent / "test" / "fixtures" / "github.voided.private-key.pem"
    ).read_text()


@pytest.fixture
def github_installation_id() -> str:
    return "8912353"


@pytest.fixture
def api_client(mocker: MockFixture, github_installation_id: str) -> Client:
    client = Client(installation_id=github_installation_id, owner="foo", repo="foo")
    mocker.patch.object(client, "send_query")
    return client


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
def block_event() -> EventInfoResponse:
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
        delete_branch_on_merge=True,
        is_private=True,
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
        restrictsPushes=True,
        pushAllowances=NodeListPushAllowance(
            nodes=[
                PushAllowance(actor=PushAllowanceActor(databaseId=None)),
                PushAllowance(actor=PushAllowanceActor(databaseId=53453)),
            ]
        ),
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
        subscription=Subscription(
            account_id="D1606A79-A1A1-4550-BA7B-C9ED0D792B1E", subscription_blocker=None
        ),
        branch_protection=branch_protection,
        review_requests=[
            PRReviewRequest(name="ghost"),
            PRReviewRequest(name="ghost-team"),
            PRReviewRequest(name="ghost-mannequin"),
        ],
        reviews=[
            PRReview(
                createdAt=arrow.get("2019-05-22T15:29:34Z").datetime,
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:29:52Z").datetime,
                state=PRReviewState.CHANGES_REQUESTED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:30:52Z").datetime,
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="kodiak", permission=Permission.ADMIN),
            ),
            PRReview(
                createdAt=arrow.get("2019-05-22T15:43:17Z").datetime,
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=arrow.get("2019-05-23T15:13:29Z").datetime,
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="walrus", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=arrow.get("2019-05-24T10:21:32Z").datetime,
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="kodiakhq", permission=Permission.WRITE),
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


@pytest.fixture  # type: ignore
@pytest.mark.asyncio
async def setup_redis(github_installation_id: str) -> None:
    r = await asyncio_redis.Connection.create(
        host=conf.REDIS_URL.hostname,
        port=conf.REDIS_URL.port,
        password=(
            conf.REDIS_URL.password.encode() if conf.REDIS_URL.password else None
        ),
    )
    key = f"kodiak:subscription:{github_installation_id}"
    await r.hset(key, "account_id", "D1606A79-A1A1-4550-BA7B-C9ED0D792B1E")
    await r.hset(key, "subscription_blocker", "")
    yield
    await r.delete([key])
    r.close()


# TODO: serialize EventInfoResponse to JSON to parametrize test
@pytest.mark.asyncio
async def test_get_event_info_blocked(
    api_client: Client,
    blocked_response: dict,
    block_event: EventInfoResponse,
    mocker: MockFixture,
    setup_redis: object,
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

    async def get_permissions_for_username_patch(username: str) -> Permission:
        if username in ("walrus", "ghost"):
            return Permission.WRITE
        if username in ("kodiak",):
            return Permission.ADMIN
        raise Exception

    mocker.patch.object(
        api_client, "get_permissions_for_username", get_permissions_for_username_patch
    )

    res = await api_client.get_event_info(branch_name="master", pr_number=100)
    assert res is not None
    assert res == block_event


MOCK_HEADERS = dict(
    Authorization="token some-json-web-token",
    Accept="application/vnd.github.machine-man-preview+json,application/vnd.github.antiope-preview+json",
)


@pytest.fixture
def mock_get_token_for_install(mocker: MockFixture) -> None:
    mocker.patch(
        "kodiak.queries.get_token_for_install", return_value=wrap_future(MOCK_HEADERS)
    )


@pytest.mark.asyncio
async def test_get_permissions_for_username_missing(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    not_found = Response()
    not_found.status_code = 404
    mocker.patch("kodiak.queries.http.Session.get", return_value=wrap_future(not_found))
    async with api_client as api_client:
        res = await api_client.get_permissions_for_username("_invalid_username")
    assert res == Permission.NONE


PERMISSION_OK_READ_USER_RESPONSE = json.dumps(
    {
        "permission": "read",
        "user": {
            "login": "ghost",
            "id": 10137,
            "node_id": "MDQ6VXNlcjEwMTM3",
            "avatar_url": "https://avatars3.githubusercontent.com/u/10137?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/ghost",
            "html_url": "https://github.com/ghost",
            "followers_url": "https://api.github.com/users/ghost/followers",
            "following_url": "https://api.github.com/users/ghost/following{/other_user}",
            "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
            "organizations_url": "https://api.github.com/users/ghost/orgs",
            "repos_url": "https://api.github.com/users/ghost/repos",
            "events_url": "https://api.github.com/users/ghost/events{/privacy}",
            "received_events_url": "https://api.github.com/users/ghost/received_events",
            "type": "User",
            "site_admin": False,
        },
    }
).encode()


@pytest.mark.asyncio
async def test_get_permissions_for_username_read(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    response = Response()
    response.status_code = 200
    response._content = PERMISSION_OK_READ_USER_RESPONSE

    mocker.patch("kodiak.queries.http.Session.get", return_value=wrap_future(response))
    async with api_client as api_client:
        res = await api_client.get_permissions_for_username("ghost")
    assert res == Permission.READ


def create_fake_redis_reply(res: Dict[bytes, bytes]) -> Any:
    class FakeDictReply:
        @staticmethod
        async def asdict() -> Any:
            return res

    class FakeRedis:
        @staticmethod
        async def hgetall(key: bytes) -> Any:
            return FakeDictReply

    return FakeRedis


@pytest.mark.asyncio
async def test_get_subscription_missing_blocker(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"",
        }
    )
    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


@pytest.mark.asyncio
async def test_get_subscription_missing_blocker_fully(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply({})
    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res is None


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b'{"kind":"seats_exceeded", "allowed_user_ids": [5234234]}',
        }
    )
    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[5234234]),
    )


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded_missing_data(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
        }
    )

    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded_invalid_data(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b"*(invalid-data4#",
        }
    )

    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded_invalid_kind(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b'{"kind":"trial_expired", "allowed_user_ids": [5234234]}',
        }
    )

    mocker.patch(
        "kodiak.event_handlers.get_redis", return_value=wrap_future(fake_redis)
    )
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )
