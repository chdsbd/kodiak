import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, cast

import asyncio_redis
import pytest
from httpx import Request, Response
from pytest_mock import MockFixture

from kodiak import app_config as conf
from kodiak.config import V1, Merge, MergeMethod
from kodiak.queries import (
    Actor,
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    Client,
    Commit,
    EventInfoResponse,
    GraphQLResponse,
    MergeableState,
    MergeStateStatus,
    NodeListPushAllowance,
    Permission,
    PRReview,
    PRReviewAuthor,
    PRReviewAuthorSchema,
    PRReviewRequest,
    PRReviewSchema,
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
    get_commits,
)
from kodiak.queries.commits import CommitConnection, GitActor
from kodiak.test_utils import wrap_future
from kodiak.tests.fixtures import FakeThottler, create_commit, requires_redis


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
    mocker.patch(
        "kodiak.queries.get_thottler_for_installation", return_value=FakeThottler()
    )
    client = Client(installation_id=github_installation_id, owner="foo", repo="foo")
    mocker.patch.object(client, "send_query")
    return client


@pytest.mark.asyncio
async def test_get_config_for_ref_error(
    api_client: Client, mocker: MockFixture
) -> None:
    """
    We should return None when there is an error.
    """
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(dict(data=None, errors=[{"test": 123}])),
    )

    res = await api_client.get_config_for_ref(ref="main")
    assert res is None


@pytest.mark.asyncio
async def test_get_config_for_ref_dot_github(
    api_client: Client, mocker: MockFixture
) -> None:
    """
    We should be able to parse from .github/.kodiak.toml
    """
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(
            dict(
                data=dict(
                    repository=dict(
                        rootConfigFile=None,
                        githubConfigFile=dict(
                            text="# .github/.kodiak.toml\nversion = 1\nmerge.method = 'rebase'"
                        ),
                    )
                )
            )
        ),
    )

    res = await api_client.get_config_for_ref(ref="main")
    assert res is not None
    assert isinstance(res.parsed, V1) and res.parsed.merge.method == MergeMethod.rebase


@pytest.fixture
def blocked_response() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
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
        requiresCodeOwnerReviews=False,
        requiresCommitSignatures=False,
        requiresConversationResolution=False,
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
                createdAt=datetime.fromisoformat("2019-05-22T15:29:34+00:00"),
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-22T15:29:52+00:00"),
                state=PRReviewState.CHANGES_REQUESTED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-22T15:30:52+00:00"),
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthor(login="kodiak", permission=Permission.ADMIN),
            ),
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-22T15:43:17+00:00"),
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-23T15:13:29+00:00"),
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="walrus", permission=Permission.WRITE),
            ),
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-24T10:21:32+00:00"),
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
        valid_merge_methods=[MergeMethod.squash],
    )


@pytest.fixture  # type: ignore
@pytest.mark.asyncio
async def setup_redis(github_installation_id: str) -> None:
    host = conf.REDIS_URL.hostname
    port = conf.REDIS_URL.port
    assert host and port
    r = await asyncio_redis.Connection.create(
        host=host,
        port=port,
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
@requires_redis
@pytest.mark.asyncio
async def test_get_event_info_blocked(
    api_client: Client,
    blocked_response: Dict[str, Any],
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

    res = await api_client.get_event_info(pr_number=100)
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
    not_found = Response(status_code=404, request=Request(method="", url=""))
    mocker.patch(
        "kodiak.queries.http.AsyncClient.get", return_value=wrap_future(not_found)
    )
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
    response = Response(
        status_code=200,
        content=PERMISSION_OK_READ_USER_RESPONSE,
        request=Request(method="", url=""),
    )

    mocker.patch(
        "kodiak.queries.http.AsyncClient.get", return_value=wrap_future(response)
    )
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
    """
    We set subscription_blocker to empty string from the web_api. This should be
    consider equivalent to a missing subscription blocker.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"",
        }
    )
    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


@pytest.mark.asyncio
async def test_get_subscription_missing_blocker_and_data(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    Check with empty string for data
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"",
            b"data": b"",
        }
    )
    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


@pytest.mark.asyncio
async def test_get_subscription_missing_blocker_fully(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    If a user is new to Kodiak we will not have set subscription information in
    Redis. We should handle this case by returning an empty subscription.
    """
    fake_redis = create_fake_redis_reply({})
    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res is None


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    When a user exceeds their seat we will specify allowed users for those users
    that occupy a seat.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b'{"kind":"seats_exceeded", "allowed_user_ids": [5234234]}',
        }
    )
    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[5234234]),
    )


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded_no_seats(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    When an account has 0 seats we will not have any allowed_user_ids.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b'{"kind":"seats_exceeded", "allowed_user_ids": []}',
        }
    )
    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


@pytest.mark.asyncio
async def test_get_subscription_seats_exceeded_missing_data(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    For backwards compatibility we cannot guarantee that "seats_exceeded" will
    have the data parameter.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
        }
    )

    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
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
    """
    Handle invalid data gracefully.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b"*(invalid-data4#",
        }
    )

    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
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
    """
    Handle mismatch in subscription_blocker types between data parameter and
    subscription_blocker.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"seats_exceeded",
            b"data": b'{"kind":"trial_expired", "allowed_user_ids": [5234234]}',
        }
    )

    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


@pytest.mark.asyncio
async def test_get_subscription_unknown_blocker(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    Handle unknown blocker by allowing user access.
    """
    fake_redis = create_fake_redis_reply(
        {
            b"account_id": b"DF5C23EB-585B-4031-B082-7FF951B4DE15",
            b"subscription_blocker": b"invalid_subscription_blocker",
        }
    )

    mocker.patch("kodiak.queue.get_redis", return_value=wrap_future(fake_redis))
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


def test_get_commits() -> None:
    """
    Verify we parse commit authors correctly. We should handle the nullability
    of name and databaseId.
    """
    pull_request_data = {
        "commitHistory": {
            "nodes": [
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": "Christopher Dignam",
                                "databaseId": 1929960,
                                "login": "chdsbd",
                                "type": "User",
                            }
                        },
                    }
                },
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": "b-lowe",
                                "databaseId": 5345234,
                                "login": "b-lowe",
                                "type": "User",
                            }
                        },
                    }
                },
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": None,
                                "databaseId": 435453,
                                "login": "kodiakhq",
                                "type": "Bot",
                            }
                        },
                    }
                },
                {"commit": {"parents": {"totalCount": 1}, "author": {"user": None}}},
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": "Christopher Dignam",
                                "databaseId": 1929960,
                                "login": "chdsbd",
                                "type": "User",
                            }
                        },
                    }
                },
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": None,
                                "databaseId": None,
                                "login": "j-doe",
                                "type": "SomeGitActor",
                            }
                        },
                    }
                },
            ]
        }
    }
    res = get_commits(pr=pull_request_data)
    assert res == [
        create_commit(
            name="Christopher Dignam", database_id=1929960, login="chdsbd", type="User"
        ),
        create_commit(name="b-lowe", database_id=5345234, login="b-lowe", type="User"),
        create_commit(name=None, database_id=435453, login="kodiakhq", type="Bot"),
        Commit(parents=CommitConnection(totalCount=1), author=GitActor(user=None)),
        create_commit(
            name="Christopher Dignam", database_id=1929960, login="chdsbd", type="User"
        ),
        create_commit(name=None, database_id=None, login="j-doe", type="SomeGitActor"),
    ]


def test_get_commits_error_handling() -> None:
    """
    We should handle parsing errors without raising an exception.
    """
    pull_request_data = {
        "commitHistory": {
            "nodes": [
                {"commit": {"parents": {"totalCount": 1}, "author": {"user": None}}},
                {"commit": {"parents": {"totalCount": 1}, "author": None}},
                {
                    "commit": {
                        "parents": {"totalCount": 3},
                        "author": {
                            "user": {
                                "name": None,
                                "databaseId": 435453,
                                "login": "kodiakhq",
                                "type": "Bot",
                            }
                        },
                    }
                },
                {
                    "commit": {
                        "parents": {"totalCount": 1},
                        "author": {
                            "user": {
                                "name": "Christopher Dignam",
                                "databaseId": 1929960,
                                "login": "chdsbd",
                                "type": "User",
                            }
                        },
                    }
                },
                {
                    "commit": {
                        "parents": {"totalCount": 2},
                        "author": {
                            "user": {
                                "name": None,
                                "databaseId": None,
                                "login": "j-doe",
                                "type": "SomeGitActor",
                            }
                        },
                    }
                },
            ]
        }
    }
    res = get_commits(pr=pull_request_data)
    assert res == [
        Commit(parents=CommitConnection(totalCount=1), author=GitActor(user=None)),
        Commit(parents=CommitConnection(totalCount=1), author=None),
        create_commit(
            name=None, database_id=435453, login="kodiakhq", type="Bot", parents=3
        ),
        create_commit(
            name="Christopher Dignam",
            database_id=1929960,
            login="chdsbd",
            type="User",
            parents=1,
        ),
        create_commit(
            name=None, database_id=None, login="j-doe", type="SomeGitActor", parents=2
        ),
    ]


def test_get_commits_error_handling_missing_response() -> None:
    """
    We should handle parsing errors without raising an exception.
    """
    pull_request_data = {"commitHistory": None}
    res = get_commits(pr=pull_request_data)
    assert res == []


@pytest.mark.asyncio
async def test_get_reviewers_and_permissions_empty_author(
    mocker: MockFixture, api_client: Client
) -> None:
    """
    We should ignore reviews with missing authors.

    `author` becomes null if the GitHub user's account is deleted. This is shown
    in the GitHub UI as the "ghost" user.
    """

    async def get_permissions_for_username_patch(username: str) -> Permission:
        if username == "jdoe":
            return Permission.WRITE
        raise Exception

    mocker.patch.object(
        api_client, "get_permissions_for_username", get_permissions_for_username_patch
    )
    res = await api_client.get_reviewers_and_permissions(
        reviews=[
            PRReviewSchema(
                createdAt=datetime.fromisoformat("2019-05-22T15:29:34+00:00"),
                state=PRReviewState.COMMENTED,
                author=PRReviewAuthorSchema(login="jdoe", type=Actor.User),
            ),
            PRReviewSchema(
                createdAt=datetime.fromisoformat("2019-05-22T15:29:52+00:00"),
                state=PRReviewState.APPROVED,
                author=None,
            ),
        ]
    )
    assert res == [
        PRReview(
            createdAt=datetime.fromisoformat("2019-05-22T15:29:34+00:00"),
            state=PRReviewState.COMMENTED,
            author=PRReviewAuthor(login="jdoe", permission=Permission.WRITE),
        )
    ]


def generate_page_of_prs(numbers: Iterable[int]) -> Response:
    """
    Create a fake page for the list-pull-requests API.

    This is used by get_open_pull_requests.
    """
    prs = [{"number": number, "base": {"ref": "main"}} for number in numbers]
    return Response(
        status_code=200,
        content=json.dumps(prs).encode(),
        request=Request(method="", url=""),
    )


@pytest.mark.asyncio
async def test_get_open_pull_requests(
    mocker: MockFixture, api_client: Client, mock_get_token_for_install: None
) -> None:
    """
    We should stop calling the API after reaching an empty page.
    """
    patched_session_get = mocker.patch(
        "kodiak.queries.http.AsyncClient.get",
        side_effect=[
            wrap_future(generate_page_of_prs(range(1, 101))),
            wrap_future(generate_page_of_prs(range(101, 201))),
            wrap_future(generate_page_of_prs(range(201, 251))),
            wrap_future(generate_page_of_prs([])),
        ],
    )

    async with api_client as api_client:
        res = await api_client.get_open_pull_requests()

    assert res is not None
    assert len(res) == 250
    assert patched_session_get.call_count == 4


@pytest.mark.asyncio
async def test_get_open_pull_requests_page_limit(
    mocker: MockFixture, api_client: Client, mock_get_token_for_install: None
) -> None:
    """
    We should fetch at most 20 pages.
    """
    pages = [range(n, n + 100) for n in range(1, 3001, 100)]
    assert len(pages) == 30
    patched_session_get = mocker.patch(
        "kodiak.queries.http.AsyncClient.get",
        side_effect=[wrap_future(generate_page_of_prs(p)) for p in pages],
    )

    async with api_client as api_client:
        res = await api_client.get_open_pull_requests()
    assert res is not None
    assert len(res) == 2000
    assert patched_session_get.call_count == 20, "stop calling after 20 pages"
