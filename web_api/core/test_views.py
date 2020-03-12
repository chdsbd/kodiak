import datetime
from typing import Any, cast

import pytest
import responses
from django.conf import settings

from core.models import (
    Account,
    AccountMembership,
    PullRequestActivity,
    User,
    UserPullRequestActivity,
)
from core.testutils import TestClient as Client


@pytest.fixture
def user() -> User:
    return cast(
        User,
        User.objects.create(
            github_id=10137,
            github_login="ghost",
            github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
        ),
    )


@pytest.fixture
def other_user() -> User:
    return cast(
        User,
        User.objects.create(
            github_id=67647,
            github_login="bear",
            github_access_token="D2F92D26-BC64-427C-93CC-13E7110F3EB7",
        ),
    )


@pytest.fixture
def mocked_responses() -> Any:
    with responses.RequestsMock() as rsps:
        yield rsps


def test_environment() -> None:
    assert settings.KODIAK_API_GITHUB_CLIENT_ID == "Iv1.111FAKECLIENTID111"
    assert settings.KODIAK_API_GITHUB_CLIENT_SECRET == "888INVALIDSECRET8888"


@pytest.fixture
def authed_client(client: Client, user: User) -> Client:
    client.login(user)
    return client


@pytest.mark.django_db
def test_usage_billing(authed_client: Client, user: User, other_user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login=user.github_login,
        github_user_id=user.github_id,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=True
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=True
    )

    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["activeUsers"] == [
        dict(
            id=user.github_id,
            name=user.github_login,
            profileImgUrl=user.profile_image(),
            interactions=1,
            lastActiveDate="2020-12-05",
        )
    ]


@pytest.mark.django_db
def test_usage_billing_authentication(authed_client: Client, other_user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 404


@pytest.mark.django_db
def test_activity(authed_client: Client, user: User,) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    pull_request_activity = PullRequestActivity.objects.create(
        date=datetime.date(2020, 2, 3),
        total_opened=15,
        total_merged=13,
        total_closed=2,
        kodiak_approved=3,
        kodiak_merged=12,
        kodiak_updated=2,
        github_installation_id=user_account.github_installation_id,
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 200
    assert res.json()["kodiakActivity"]["labels"] == ["2020-02-03"]
    assert res.json()["kodiakActivity"]["datasets"] == {
        "approved": [pull_request_activity.kodiak_approved],
        "merged": [pull_request_activity.kodiak_merged],
        "updated": [pull_request_activity.kodiak_updated],
    }
    assert res.json()["pullRequestActivity"]["labels"] == ["2020-02-03"]
    assert res.json()["pullRequestActivity"]["datasets"] == {
        "opened": [pull_request_activity.total_opened],
        "merged": [pull_request_activity.total_merged],
        "closed": [pull_request_activity.total_closed],
    }


@pytest.mark.django_db
def test_activity_authentication(authed_client: Client, other_user: User,) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 404


@pytest.mark.django_db
def test_sync_accounts_success(
    authed_client: Client, successful_sync_accounts_response: object
) -> None:
    assert Account.objects.count() == 0
    res = authed_client.post("/v1/sync_accounts")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert Account.objects.count() == 1


@pytest.mark.django_db
def test_sync_accounts_failure(
    authed_client: Client, failing_sync_accounts_response: object
) -> None:
    assert Account.objects.count() == 0
    res = authed_client.post("/v1/sync_accounts")
    assert res.status_code == 200
    assert res.json()["ok"] is False
    assert Account.objects.count() == 0


@pytest.mark.django_db
def test_current_account(authed_client: Client, user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = Account.objects.create(
        github_installation_id=83676,
        github_account_id=779874,
        github_account_login="recipeyak",
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=org_account, user=user, role="member")

    res = authed_client.get(f"/v1/t/{org_account.id}/current_account")
    assert res.status_code == 200
    assert res.json()["user"]["id"] == str(user.id)
    assert res.json()["user"]["name"] == user.github_login
    assert (
        res.json()["user"]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user.github_id}"
    )
    assert res.json()["org"]["id"] == str(org_account.id)
    assert res.json()["org"]["name"] == org_account.github_account_login
    assert (
        res.json()["org"]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{org_account.github_account_id}"
    )

    assert len(res.json()["accounts"]) == 2
    accounts = sorted(res.json()["accounts"], key=lambda x: x["name"])
    assert accounts[0]["id"] == str(user_account.id)
    assert accounts[0]["name"] == user_account.github_account_login
    assert (
        accounts[0]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user_account.github_account_id}"
    )


@pytest.mark.django_db
def test_current_account_authentication(
    authed_client: Client, other_user: User,
) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/current_account")
    assert res.status_code == 404


@pytest.mark.django_db
def test_accounts(authed_client: Client, user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = Account.objects.create(
        github_installation_id=83676,
        github_account_id=779874,
        github_account_login="recipeyak",
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=org_account, user=user, role="member")

    res = authed_client.get("/v1/accounts")
    assert res.status_code == 200
    assert len(res.json()) == 2
    accounts = sorted(res.json(), key=lambda x: x["name"])
    assert accounts[0]["id"] == str(user_account.id)
    assert accounts[0]["name"] == user_account.github_account_login
    assert (
        accounts[0]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user_account.github_account_id}"
    )


@pytest.mark.django_db
def test_logout(client: Client, user: User) -> None:
    """
    Ensure we delete the cookie on logout.
    The user should no longer be able to access authed routes.
    """
    client.login(user)
    res = client.get("/v1/ping")
    assert res.status_code == 200
    res = client.get("/v1/logout")
    assert res.status_code == 201
    res = client.get("/v1/ping")
    assert res.status_code == 401


@pytest.mark.django_db
def test_oauth_login(client: Client, state_token: str) -> None:
    res = client.get("/v1/oauth_login", dict(state=state_token))
    assert res.status_code == 302
    assert (
        res["Location"]
        == f"https://github.com/login/oauth/authorize?client_id=Iv1.111FAKECLIENTID111&redirect_uri=https://app.kodiakhq.com/oauth&state={state_token}"
    )


@pytest.fixture
def successful_sync_accounts_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "total_count": 1,
            "installations": [
                {
                    "id": 1066615,
                    "account": {
                        "login": "chdsbd",
                        "id": 1929960,
                        "node_id": "MDQ6VXNlcjE5Mjk5NjA=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/1929960?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/chdsbd",
                        "html_url": "https://github.com/chdsbd",
                        "followers_url": "https://api.github.com/users/chdsbd/followers",
                        "following_url": "https://api.github.com/users/chdsbd/following{/other_user}",
                        "gists_url": "https://api.github.com/users/chdsbd/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/chdsbd/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/chdsbd/subscriptions",
                        "organizations_url": "https://api.github.com/users/chdsbd/orgs",
                        "repos_url": "https://api.github.com/users/chdsbd/repos",
                        "events_url": "https://api.github.com/users/chdsbd/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/chdsbd/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/1066615/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/1066615",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 1929960,
                    "target_type": "User",
                    "permissions": {
                        "administration": "read",
                        "checks": "write",
                        "contents": "write",
                        "issues": "read",
                        "metadata": "read",
                        "pull_requests": "write",
                        "statuses": "read",
                    },
                    "events": [
                        "check_run",
                        "issue_comment",
                        "pull_request",
                        "pull_request_review",
                        "pull_request_review_comment",
                        "push",
                        "status",
                    ],
                    "created_at": "2019-05-26T23:47:57.000-04:00",
                    "updated_at": "2020-02-09T18:39:43.000-05:00",
                    "single_file_name": None,
                }
            ],
        },
    )


@pytest.fixture
def successful_responses(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.POST,
        "https://github.com/login/oauth/access_token",
        body="access_token=D6B5A3B57D32498DB00845A99137D3E2&token_type=bearer",
        status=200,
        content_type="application/x-www-form-urlencoded",
    )

    # https://developer.github.com/v3/users/#response-with-public-and-private-profile-information
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user",
        json={
            "login": "ghost",
            "id": 10137,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/ghost_happy.gif",
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
            "name": "monalisa ghost",
            "company": "GitHub",
            "blog": "https://github.com/blog",
            "location": "San Francisco",
            "email": "ghost@github.com",
            "hireable": False,
            "bio": "There once was...",
            "public_repos": 2,
            "public_gists": 1,
            "followers": 20,
            "following": 0,
            "created_at": "2008-01-14T04:33:35Z",
            "updated_at": "2008-01-14T04:33:35Z",
            "private_gists": 81,
            "total_private_repos": 100,
            "owned_private_repos": 100,
            "disk_usage": 10000,
            "collaborators": 8,
            "two_factor_authentication": True,
            "plan": {
                "name": "Medium",
                "space": 400,
                "private_repos": 20,
                "collaborators": 0,
            },
        },
        status=200,
    )


@pytest.mark.django_db
def test_oauth_complete_success_new_account(
    client: Client,
    state_token: str,
    successful_responses: object,
    successful_sync_accounts_response: object,
) -> None:
    assert Account.objects.count() == 0
    assert User.objects.count() == 0
    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    assert Account.objects.count() == 1
    user = User.objects.get()
    assert user.github_id == 10137
    assert user.github_login == "ghost"
    assert user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"


@pytest.mark.django_db
def test_oauth_complete_success_existing_account(
    client: Client,
    user: User,
    successful_responses: object,
    successful_sync_accounts_response: object,
    state_token: str,
) -> None:
    assert User.objects.count() == 1

    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    new_user = User.objects.get()
    assert new_user.github_id == user.github_id
    assert new_user.github_login == user.github_login
    assert new_user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"


@pytest.fixture
def failing_sync_accounts_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "message": "Bad credentials",
            "documentation_url": "https://developer.github.com/v3",
        },
        status=401,
    )


@pytest.mark.django_db
def test_oauth_complete_sync_installation_failure(
    client: Client,
    successful_responses: object,
    failing_sync_accounts_response: object,
    state_token: str,
) -> None:

    assert User.objects.count() == 0
    assert Account.objects.count() == 0
    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is False
    assert login_result["error"] == "AccountSyncFailure"
    assert (
        login_result["error_description"] == "Failed to sync GitHub accounts for user."
    )
    assert User.objects.count() == 1
    user = User.objects.get()
    assert user.github_id == 10137
    assert user.github_login == "ghost"
    assert user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"
    assert Account.objects.count() == 0


@pytest.mark.skip
def test_oauth_complete_cookie_session_mismatch(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fail_to_fetch_access_token(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fetch_access_token_qs_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fetch_access_token_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fail_fetch_github_account_info(client: Client) -> None:
    assert False


@pytest.fixture
def state_token(client: Client) -> str:
    return "71DDCF95-84FC-4A5F-BCBF-BEB5FCCBDEA8"


@pytest.mark.django_db
def test_oauth_complete_missing_code(client: Client, state_token: str) -> None:
    res = client.post(
        "/v1/oauth_complete", dict(serverState=state_token, clientState=state_token,),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is False
    assert login_result["error"] == "OAuthMissingCode"
    assert login_result["error_description"] == "Payload should have a code parameter."
