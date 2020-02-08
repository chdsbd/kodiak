import base64
import json
from typing import cast
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

import pytest
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
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


def test_environment():
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
def test_oauth_login(client: Client, mocker) -> None:
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


def test_oauth_callback_success_new_account(client: Client) -> None:
    assert False


def test_oauth_callback_success_existing_account(client: Client) -> None:
    assert False


def test_oauth_callback_cookie_session_mismatch(client: Client) -> None:
    assert False


def test_oauth_callback_fail_to_fetch_access_token(client: Client) -> None:
    assert False


def test_oauth_callback_fetch_access_token_qs_res_error(client: Client) -> None:
    assert False


def test_oauth_callback_fetch_access_token_res_error(client: Client) -> None:
    assert False


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
