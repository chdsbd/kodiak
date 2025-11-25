import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Iterable, Iterator, cast

import pytest
from pytest_mock import MockFixture

from kodiak import app_config as conf
from kodiak.config import V1, Merge, MergeMethod
from kodiak.http import Request, Response
from kodiak.queries import (
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
    ReviewThread,
    ReviewThreadConnection,
    SeatsExceeded,
    StatusContext,
    StatusState,
    Subscription,
    get_commits,
)
from kodiak.queries.commits import CommitConnection, GitActor
from kodiak.redis_client import redis_bot
from kodiak.test_utils import wrap_future
from kodiak.tests.fixtures import FakeThottler, create_commit, requires_redis


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

    res = await api_client.get_config_for_ref(ref="main", org_repo_default_branch=None)
    assert res is None


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

    res = await api_client.get_config_for_ref(ref="main", org_repo_default_branch=None)
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
        reviewThreads=ReviewThreadConnection(
            nodes=[ReviewThread(isCollapsed=True), ReviewThread(isCollapsed=False)]
        ),
    )
    rep_info = RepoInfo(
        merge_commit_allowed=False,
        rebase_merge_allowed=False,
        squash_merge_allowed=True,
        delete_branch_on_merge=True,
        is_private=True,
    )
    branch_protection = BranchProtectionRule(
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
        bot_reviews=[
            PRReview(
                createdAt=datetime.fromisoformat("2019-05-24T10:21:32+00:00"),
                state=PRReviewState.APPROVED,
                author=PRReviewAuthor(login="kodiakhq"),
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


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    # from: https://github.com/pytest-dev/pytest-asyncio/issues/38#issuecomment-264418154
    # fixes 'got Future <Future pending> attached to a different loop' type errors
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def setup_redis(github_installation_id: str) -> AsyncGenerator[None, None]:
    host = conf.REDIS_URL.hostname
    port = conf.REDIS_URL.port
    assert host and port
    key = f"kodiak:subscription:{github_installation_id}"
    await redis_bot.hset(key, "account_id", "D1606A79-A1A1-4550-BA7B-C9ED0D792B1E")
    await redis_bot.hset(key, "subscription_blocker", "")
    yield
    await redis_bot.delete(key)
    await redis_bot.close()


def msg_to_dict(msg: str) -> Dict[str, str]:
    # hack to parse the key value format from https://github.com/hynek/structlog/blob/a8936b9a6f07b5da55c4c28fc73dfab30c20a06d/src/structlog/processors.py#L107-L111
    result = re.split("'(.+?)'=", msg[::-1])
    l_iter = iter(z[::-1].strip() for z in result if z)
    return {v: k for k, v in dict(zip(l_iter, l_iter)).items()}


# TODO(sbdchd): these logs probably indicate a problem with the test setup

EXPECTED_ERRORS = [
    (
        "kodiak.queries",
        30,
        "problem parsing api features",
    ),
    ("kodiak.queries.commits", 40, "problem parsing commit authors"),
]

# TODO: serialize EventInfoResponse to JSON to parametrize test
@requires_redis
async def test_get_event_info_blocked(
    api_client: Client,
    blocked_response: Dict[str, Any],
    block_event: EventInfoResponse,
    mocker: MockFixture,
    setup_redis: object,
    caplog: Any,
) -> None:
    caplog.set_level(logging.WARNING)

    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(
            GraphQLResponse(
                data=blocked_response.get("data"), errors=blocked_response.get("errors")
            )
        ),
    )
    res = await api_client.get_event_info(pr_number=100)
    assert res is not None
    assert res == block_event

    assert [
        (mod, level, msg_to_dict(msg)["event"])
        for mod, level, msg in caplog.record_tuples
    ] == EXPECTED_ERRORS


@requires_redis
async def test_get_event_info_no_author(
    api_client: Client,
    mocker: MockFixture,
    block_event: EventInfoResponse,
    setup_redis: object,
    caplog: Any,
) -> None:
    """
    When a PR account author is deleted, the PR's author becomes null, so we
    need to handle that.
    """
    caplog.set_level(logging.WARNING)
    blocked_response = json.loads(
        (
            Path(__file__).parent
            / "test"
            / "fixtures"
            / "api"
            / "get_event"
            / "no_author.json"
        ).read_text()
    )
    block_event.pull_request.author = None
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(
            GraphQLResponse(
                data=blocked_response.get("data"), errors=blocked_response.get("errors")
            )
        ),
    )
    res = await api_client.get_event_info(pr_number=100)
    assert res == block_event

    assert [
        (mod, level, msg_to_dict(msg)["event"])
        for mod, level, msg in caplog.record_tuples
    ] == EXPECTED_ERRORS


async def test_get_event_info_no_latest_sha(
    api_client: Client,
    mocker: MockFixture,
    block_event: EventInfoResponse,
    setup_redis: object,
    caplog: Any,
) -> None:
    """
    When a PR doesn't have a changeset aka a diff, the latest_sha will be None.
    """
    caplog.set_level(logging.WARNING)
    blocked_response = json.loads(
        (
            Path(__file__).parent
            / "test"
            / "fixtures"
            / "api"
            / "get_event"
            / "no_latest_sha.json"
        ).read_text()
    )
    assert (
        len(blocked_response["data"]["repository"]["pullRequest"]["commits"]["nodes"])
        == 0
    ), "Shouldn't have any commits."
    block_event.pull_request.author = None
    mocker.patch.object(
        api_client,
        "send_query",
        return_value=wrap_future(
            GraphQLResponse(
                data=blocked_response.get("data"), errors=blocked_response.get("errors")
            )
        ),
    )
    res = await api_client.get_event_info(pr_number=100)
    assert res is None

    assert [
        (mod, level, msg_to_dict(msg)["event"])
        for mod, level, msg in caplog.record_tuples
    ] == [
        (
            "kodiak.queries",
            30,
            "problem parsing api features",
        )
    ]


MOCK_HEADERS = dict(
    Authorization="token some-json-web-token",
    Accept="application/vnd.github.machine-man-preview+json,application/vnd.github.antiope-preview+json",
)


@pytest.fixture
def mock_get_token_for_install(mocker: MockFixture) -> None:
    mocker.patch(
        "kodiak.queries.get_token_for_install", return_value=wrap_future(MOCK_HEADERS)
    )


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


def create_fake_redis_reply(res: Dict[bytes, bytes]) -> Any:
    class FakeRedis:
        @staticmethod
        async def hgetall(key: bytes) -> Any:
            return res

    return FakeRedis


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
    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


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
    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15", subscription_blocker=None
    )


async def test_get_subscription_missing_blocker_fully(
    api_client: Client, mocker: MockFixture, mock_get_token_for_install: None
) -> None:
    """
    If a user is new to Kodiak we will not have set subscription information in
    Redis. We should handle this case by returning an empty subscription.
    """
    fake_redis = create_fake_redis_reply({})
    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res is None


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
    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[5234234]),
    )


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
    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


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

    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


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

    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


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

    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
    async with api_client as api_client:
        res = await api_client.get_subscription()
    assert res == Subscription(
        account_id="DF5C23EB-585B-4031-B082-7FF951B4DE15",
        subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
    )


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

    mocker.patch("kodiak.queries.redis_web_api", fake_redis)
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
