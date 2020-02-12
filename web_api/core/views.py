from dataclasses import asdict, dataclass
from datetime import date, timedelta
from random import randint
from typing import Iterable, Optional, Union
from urllib.parse import parse_qsl

import requests
from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
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


@auth.login_required
def usage_billing(request: HttpRequest, team_id: str) -> HttpResponse:
    return JsonResponse(
        dict(
            activeUserCount=8,
            nextBillingDate="February 17th, 2019",
            billingPeriod=dict(start="Jan 17", end="Feb 16"),
            activeUsers=[
                dict(
                    id=1929960,
                    name="chdsbd",
                    profileImgUrl="https://avatars0.githubusercontent.com/u/1929960?s=460&v=4",
                    interactions=4,
                    lastActiveDate="Feb 10",
                )
            ],
            perUserUSD=5,
            perMonthUSD=75,
        )
    )


@dataclass
class ActivityDay:
    date: date
    approved: int = 0
    merged: int = 0
    updated: int = 0


def events_to_chart(events: Iterable[ActivityDay]) -> dict:
    labels = []
    approved = []
    merged = []
    updated = []
    for event in events:
        labels.append(event.date)
        approved.append(event.approved)
        merged.append(event.merged)
        updated.append(event.updated)
    return dict(
        labels=labels, datasets=dict(approved=approved, merged=merged, updated=updated)
    )


@auth.login_required
def activity(request: HttpRequest, team_id: str) -> HttpResponse:
    today = date.today()
    dates = [ActivityDay(date=today, approved=2, merged=3, updated=2)]
    for x in range(60):
        dates.append(
            ActivityDay(
                date=today - timedelta(days=(x + 1)),
                approved=randint(0, 10),
                merged=randint(0, 10),
                updated=randint(0, 10),
            )
        )

    chart = events_to_chart(reversed(dates))
    return JsonResponse(dict(kodiakActivity=chart, pullRequestActivity=chart))


@auth.login_required
def current_account(request: HttpRequest) -> HttpResponse:
    return JsonResponse(
        dict(
            user=dict(
                id=7340772,
                name="sbdchd",
                profileImgUrl="https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            ),
            org=dict(
                id=29196,
                name="kodiakhq[bot]",
                profileImgUrl="https://avatars1.githubusercontent.com/in/29196?v=4",
            ),
            accounts=[
                dict(
                    id=7340772,
                    name="sbdchd",
                    profileImgUrl="https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
                ),
                dict(
                    id=32210060,
                    name="recipeyak",
                    profileImgUrl="https://avatars1.githubusercontent.com/u/32210060?s=400&v=4",
                ),
                dict(
                    id=7806836,
                    name="AdmitHub",
                    profileImgUrl="https://avatars1.githubusercontent.com/u/7806836?s=400&v=4",
                ),
                dict(
                    id=33015070,
                    name="getdoug",
                    profileImgUrl="https://avatars0.githubusercontent.com/u/33015070?s=200&v=4",
                ),
                dict(
                    id=8897583,
                    name="pytest-dev",
                    profileImgUrl="https://avatars1.githubusercontent.com/u/8897583?s=200&v=4",
                ),
            ],
        )
    )


@auth.login_required
def accounts(request: HttpRequest) -> HttpResponse:
    return JsonResponse(
        [
            dict(
                id=7340772,
                name="sbdchd",
                profileImgUrl="https://avatars1.githubusercontent.com/u/7340772?s=400&v=4",
            ),
            dict(
                id=32210060,
                name="recipeyak",
                profileImgUrl="https://avatars1.githubusercontent.com/u/32210060?s=400&v=4",
            ),
            dict(
                id=7806836,
                name="AdmitHub",
                profileImgUrl="https://avatars1.githubusercontent.com/u/7806836?s=400&v=4",
            ),
            dict(
                id=33015070,
                name="getdoug",
                profileImgUrl="https://avatars0.githubusercontent.com/u/33015070?s=200&v=4",
            ),
            dict(
                id=8897583,
                name="pytest-dev",
                profileImgUrl="https://avatars1.githubusercontent.com/u/8897583?s=200&v=4",
            ),
        ],
        safe=False,
    )


def oauth_login(request: HttpRequest) -> HttpResponse:
    """
    Entry point to oauth flow.

    We keep this as a simple endpoint on the API to redirect users to from the
    frontend. This way we keep complexity within the API.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#1-request-a-users-github-identity
    """
    state = request.GET.get("state")
    if not state:
        return HttpResponseBadRequest("Missing required state parameter")
    oauth_url = URL("https://github.com/login/oauth/authorize").with_query(
        dict(
            client_id=settings.KODIAK_API_GITHUB_CLIENT_ID,
            redirect_uri=settings.KODIAK_WEB_AUTHED_LANDING_PATH,
            state=state,
        )
    )
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
    session_oauth_state = request.POST.get("serverState", None)
    request_oauth_state = request.POST.get("clientState", None)
    if (
        not session_oauth_state
        or not request_oauth_state
        or session_oauth_state != request_oauth_state
    ):
        return Error(
            error="OAuthStateMismatch",
            error_description="State parameters must match.",
        )

    # handle errors
    if request.POST.get("error"):
        return Error(
            error=request.POST.get("error"),
            error_description=request.POST.get("error_description"),
        )

    code = request.POST.get("code")
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
    access_token_error = access_res_data.get("error")
    if access_token_error:
        return Error(
            error=access_token_error,
            error_description=access_res_data.get("error_description", ""),
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
        existing_user.save()
        user = existing_user
    else:
        user = User.objects.create(
            github_id=github_account_id,
            github_login=github_login,
            github_access_token=access_token,
        )

    auth.login(user, request)
    return Success()


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def oauth_complete(request: HttpRequest) -> HttpResponse:
    """
    OAuth callback handler from GitHub.
    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.
    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    if request.method == "POST":
        login_result = process_login_request(request)
        return JsonResponse(asdict(login_result))
    return HttpResponse()


@csrf_exempt
def logout(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    request.user = AnonymousUser()
    return HttpResponse(status=201)
