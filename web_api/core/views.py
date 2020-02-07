from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse

from core import auth
from core.models import AnonymousUser, User


@dataclass(init=False)
class APIException(Exception):
    code: int = 500
    message: str = "Internal Server Error"

    def __init__(
        self, message: Optional[str] = None, code: Optional[int] = None
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code


class BadRequest(APIException):
    message: str = "Your request is invalid."
    code: int = 400

@auth.login_required
def ping(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": True})

@auth.login_required
def installations(request: HttpRequest) -> HttpResponse:
    return JsonResponse([{"id": 53121}], safe=False)


def oauth_login(request: HttpRequest) -> HttpResponse:
    """
    Entry point to oauth flow.

    We keep this as a simple endpoint on the API to redirect users to from the
    frontend. This way we keep complexity within the API.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#1-request-a-users-github-identity
    """
    return HttpResponseRedirect(str(auth.get_oauth_url()))


# TODO: handle deauthorization webhook
# https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#handling-a-revoked-github-app-authorization


def oauth_callback(request: HttpRequest) -> HttpResponse:
    """
    OAuth callback handler from GitHub.
    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.
    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    code = request.GET.get("code")
    if code is None:
        raise BadRequest("Missing code parameter")
    payload = dict(
        client_id=settings.KODIAK_API_GITHUB_CLIENT_ID,
        client_secret=settings.KODIAK_API_GITHUB_CLIENT_SECRET,
        code=code,
    )
    access_res = requests.post("https://github.com/login/oauth/access_token", payload)
    access_res.raise_for_status()

    query_string = parse_qs(access_res.text)
    assert (
        query_string.get("error") is None
    ), "we should not have an error response when logging in"
    access_token = query_string["access_token"][0]

    # fetch information about the user using their oauth access token.
    user_res = requests.get(
        "https://api.github.com/user",
        headers=dict(authorization=f"Bearer {access_token}"),
    )
    github_login = user_res.json()["login"]
    github_account_id = int(user_res.json()["id"])

    existing_user: Optional[User] = User.objects.filter(
        github_id=github_account_id
    ).first()
    if existing_user:
        existing_user.github_login = github_login
        existing_user.github_access_token = access_token
        user = existing_user
    else:
        User.objects.create(
            github_id=github_account_id,
            github_login=github_login,
            github_access_token=access_token,
        )

    auth.login(user, request)
    return HttpResponseRedirect(settings.KODIAK_WEB_AUTHED_LANDING_PATH)


def logout(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    request.user = AnonymousUser()
    return HttpResponse(status=201)
