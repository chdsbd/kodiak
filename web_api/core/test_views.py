import base64
import json
from typing import Any, cast
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

import pytest
import responses
from django.conf import settings
from django.http import HttpResponse

from core.models import User
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
def mocked_responses() -> Any:
    with responses.RequestsMock() as rsps:
        yield rsps


def test_environment() -> None:
    assert settings.KODIAK_API_GITHUB_CLIENT_ID == "Iv1.111FAKECLIENTID111"
    assert settings.KODIAK_API_GITHUB_CLIENT_SECRET == "888INVALIDSECRET8888"


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
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_installations(client: Client, user: User) -> None:
    """
    Authentication should be restricted to logged in users.
    """
    res = client.get("/v1/installations")
    assert res.status_code in (401, 403)

    client.login(user)
    res = client.get("/v1/installations")

    assert res.status_code == 200


@pytest.mark.django_db
def test_oauth_login(client: Client, mocker: Any) -> None:
    mocker.patch(
        "core.views.uuid.uuid4",
        return_value=UUID("8d34e38a-91a2-426e-9276-a98c06bd3c2f"),
    )
    res = client.get("/v1/oauth_login")
    assert res.status_code == 302
    assert (
        res["Location"]
        == "https://github.com/login/oauth/authorize?client_id=Iv1.111FAKECLIENTID111&redirect_uri=http://testserver/v1/oauth_callback&state=8d34e38a-91a2-426e-9276-a98c06bd3c2f"
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
            "login": "octocat",
            "id": 13221,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/octocat_happy.gif",
            "gravatar_id": "",
            "url": "https://api.github.com/users/octocat",
            "html_url": "https://github.com/octocat",
            "followers_url": "https://api.github.com/users/octocat/followers",
            "following_url": "https://api.github.com/users/octocat/following{/other_user}",
            "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
            "organizations_url": "https://api.github.com/users/octocat/orgs",
            "repos_url": "https://api.github.com/users/octocat/repos",
            "events_url": "https://api.github.com/users/octocat/events{/privacy}",
            "received_events_url": "https://api.github.com/users/octocat/received_events",
            "type": "User",
            "site_admin": False,
            "name": "monalisa octocat",
            "company": "GitHub",
            "blog": "https://github.com/blog",
            "location": "San Francisco",
            "email": "octocat@github.com",
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
def test_oauth_callback_success_new_account(
    client: Client, state_token: str, successful_responses: object
) -> None:

    assert User.objects.count() == 0
    res = client.get(
        f"/v1/oauth_callback?state={state_token}&code=D86BE2B3F3C74ACB91D3DF7B649F40BB"
    )
    assert res.status_code == 302

    login_result = get_result(res)
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    user = User.objects.get()
    assert user.github_id == 13221
    assert user.github_login == "octocat"
    assert user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"


@pytest.mark.django_db
def test_oauth_callback_success_existing_account(
    client: Client, user: User, successful_responses: object
) -> None:
    assert User.objects.count() == 1

    res = client.get(
        f"/v1/oauth_callback?state={state_token}&code=D86BE2B3F3C74ACB91D3DF7B649F40BB"
    )
    assert res.status_code == 302

    login_result = get_result(res)
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    new_user = User.objects.get()
    assert new_user.github_id == user.github_id
    assert new_user.github_login == user.github_login
    assert new_user.github_access_token == user.github_access_token


@pytest.mark.skip
def test_oauth_callback_cookie_session_mismatch(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_callback_fail_to_fetch_access_token(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_callback_fetch_access_token_qs_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_callback_fetch_access_token_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_callback_fail_fetch_github_account_info(client: Client) -> None:
    assert False


def get_result(res: HttpResponse) -> dict:
    return cast(
        dict,
        json.loads(
            base64.b32decode(
                dict(parse_qsl(urlsplit(res["Location"]).query))["login_result"]
            ).decode()
        ),
    )


@pytest.fixture
def state_token(client: Client) -> str:
    state_token = "71DDCF95-84FC-4A5F-BCBF-BEB5FCCBDEA8"
    session = client.session
    session["oauth_login_state"] = state_token
    session.save()
    return state_token


@pytest.mark.django_db
def test_oauth_callback_missing_code(client: Client, state_token: str) -> None:
    res = client.get(f"/v1/oauth_callback?state={state_token}")
    assert res.status_code == 302

    login_result = get_result(res)
    assert login_result["ok"] is False
    assert login_result["error"] == "OAuthMissingCode"
    assert login_result["error_description"] == "Payload should have a code parameter."
