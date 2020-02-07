import pytest

from core.models import User


@pytest.fixture
def user() -> User:
    return User.objects.create(
        github_id=10137,
        github_login="ghost",
        github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
    )

@pytest.mark.django_db
def test_logout(client, user: User) -> None:
    """
    Ensure we delete the cookie on logout.
    The user should no longer be able to access authed routes.
    """
    client.login(user)
    res = client.get('/v1/ping')
    assert res.status_code == 200
    res = client.get('/v1/logout')
    assert res.status_code == 201
    res = client.get('/v1/ping')
    assert res.status_code in (401, 403)

@pytest.mark.django_db
def test_installations(client, user) -> None:
    """
    Authentication should be restricted to logged in users.
    """
    res = client.get('/v1/installations')
    assert res.status_code in (401, 403)

    client.login(user)
    res = client.get('/v1/installations')
    assert res.status_code == 200
    assert res.json() == [{'id': 53121}]



def test_oauth_login(client) -> None:
    res = client.get("/v1/oauth_login")
    assert res.status_code == 302
    assert (
        res["Location"]
        == "https://github.com/login/oauth/authorize?client_id=Iv1.e6e6830e66989e33&redirect_uri=https://f9aadcfb.ngrok.io/v1/oauth_callback"
    )


@pytest.mark.skip
def test_oauth_callback(client) -> None:
    res = client.get("/v1/oauth_callback?code=4f8abe1fe98044fedc35")
    assert res.status_code == 200
    assert False

def test_oauth_callback_missing_code(client) -> None:
    res = client.get("/v1/oauth_callback")
    assert res.status_code == 400
    assert res.json()['message'] == "Missing code parameter"
