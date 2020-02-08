import base64
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Optional, Union
from urllib.parse import parse_qsl

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from typing_extensions import Literal
from yarl import URL

from core import auth
from core.models import AnonymousUser, User


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
    oauth_redirect_uri = request.build_absolute_uri(reverse("oauth_callback"))
    state = str(uuid.uuid4())
    oauth_url = URL("https://github.com/login/oauth/authorize").with_query(
        dict(
            client_id=settings.KODIAK_API_GITHUB_CLIENT_ID,
            redirect_uri=str(oauth_redirect_uri),
            state=state,
        )
    )
    request.session["oauth_login_state"] = state
    return HttpResponseRedirect(str(oauth_url))


# TODO: handle deauthorization webhook
# https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#handling-a-revoked-github-app-authorization


@dataclass
class Error:
    error: str
    error_description: str
    ok: Literal[False] = False


@dataclass
class Success:
    ok: Literal[True] = True


def process_login_request(request: HttpRequest) -> Union[Success, Error]:
    session_oauth_state = request.session.get("oauth_login_state")
    request_oauth_state = request.GET.get("state", None)
    if (
        not session_oauth_state
        or not request_oauth_state
        or session_oauth_state != request_oauth_state
    ):
        return Error(
            error="OAuthStateMismatch",
            error_description="Cookie session must match session in query parameters.",
        )

    # handle errors
    if request.GET.get("error"):
        return Error(
            error=request.GET.get("error"),
            error_description=request.GET.get("error_description"),
        )

    code = request.GET.get("code")
    if not code:
        return Error(
            error="OAuthMissingCode",
            error_description="Payload should have a code parameter.",
        )

    payload = dict(
        client_id=settings.KODIAK_API_GITHUB_CLIENT_ID,
        client_secret=settings.KODIAK_API_GITHUB_CLIENT_SECRET,
        code=code,
    )
    access_res = requests.post("https://github.com/login/oauth/access_token", payload)
    try:
        access_res.raise_for_status()
    except requests.HTTPError:
        return Error(
            error="OAuthServerError", error_description="Failed to fetch access token."
        )
    access_res_data = dict(parse_qsl(access_res.text))
    if access_res_data.get("error"):
        return Error(
            error=request.GET.get("error"),
            error_description=request.GET.get("error_description"),
        )

    access_token = access_res_data.get("access_token")
    if not access_token:
        return Error(
            error="OAuthMissingAccessToken",
            error_description="OAuth missing access token.",
        )

    # fetch information about the user using their oauth access token.
    user_data_res = requests.get(
        "https://api.github.com/user",
        headers=dict(authorization=f"Bearer {access_token}"),
    )
    try:
        user_data_res.raise_for_status()
    except requests.HTTPError:
        return Error(
            error="OAuthServerError",
            error_description="Failed to fetch account information from GitHub.",
        )
    user_data = user_data_res.json()
    github_login = user_data["login"]
    github_account_id = int(user_data["id"])

    existing_user: Optional[User] = User.objects.filter(
        github_id=github_account_id
    ).first()
    if existing_user:
        existing_user.github_login = github_login
        existing_user.github_access_token = access_token
        user = existing_user
    else:
        user = User.objects.create(
            github_id=github_account_id,
            github_login=github_login,
            github_access_token=access_token,
        )

    auth.login(user, request)
    return Success()


def oauth_callback(request: HttpRequest) -> HttpResponse:
    """
    OAuth callback handler from GitHub.
    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.
    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    login_result = process_login_request(request)
    landing_url = URL(settings.KODIAK_WEB_AUTHED_LANDING_PATH).with_query(
        login_result=base64.b32encode(
            json.dumps(asdict(login_result)).encode()
        ).decode()
    )
    return HttpResponseRedirect(str(landing_url))


def logout(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    request.user = AnonymousUser()
    return HttpResponse(status=201)
