import logging
from dataclasses import asdict, dataclass
from typing import Optional, Union
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
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from typing_extensions import Literal
from yarl import URL

from core import auth
from core.models import (
    Account,
    AnonymousUser,
    PullRequestActivity,
    SyncAccountsError,
    User,
    UserPullRequestActivity,
)

logger = logging.getLogger(__name__)


@auth.login_required
def ping(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": True})


@auth.login_required
def usage_billing(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    active_users = UserPullRequestActivity.get_active_users_in_last_30_days(account)
    return JsonResponse(
        dict(
            activeUsers=[
                dict(
                    id=active_user.github_id,
                    name=active_user.github_login,
                    profileImgUrl=active_user.profile_image(),
                    interactions=active_user.days_active,
                    lastActiveDate=active_user.last_active_at.isoformat(),
                )
                for active_user in active_users
            ],
        )
    )


@auth.login_required
def activity(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    kodiak_activity_labels = []
    kodiak_activity_approved = []
    kodiak_activity_merged = []
    kodiak_activity_updated = []

    total_labels = []
    total_opened = []
    total_merged = []
    total_closed = []
    for day_activity in PullRequestActivity.objects.filter(
        github_installation_id=account.github_installation_id
    ).order_by("date"):
        kodiak_activity_labels.append(day_activity.date)
        kodiak_activity_approved.append(day_activity.kodiak_approved)
        kodiak_activity_merged.append(day_activity.kodiak_merged)
        kodiak_activity_updated.append(day_activity.kodiak_updated)
        total_labels.append(day_activity.date)
        total_opened.append(day_activity.total_opened)
        total_merged.append(day_activity.total_merged)
        total_closed.append(day_activity.total_closed)

    return JsonResponse(
        dict(
            kodiakActivity=dict(
                labels=kodiak_activity_labels,
                datasets=dict(
                    approved=kodiak_activity_approved,
                    merged=kodiak_activity_merged,
                    updated=kodiak_activity_updated,
                ),
            ),
            pullRequestActivity=dict(
                labels=total_labels,
                datasets=dict(
                    opened=total_opened, merged=total_merged, closed=total_closed
                ),
            ),
        )
    )


@auth.login_required
def current_account(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    return JsonResponse(
        dict(
            user=dict(
                id=request.user.id,
                name=request.user.github_login,
                profileImgUrl=request.user.profile_image(),
            ),
            org=dict(
                id=account.id,
                name=account.github_account_login,
                profileImgUrl=account.profile_image(),
            ),
            accounts=[
                dict(
                    id=x.id,
                    name=x.github_account_login,
                    profileImgUrl=x.profile_image(),
                )
                for x in Account.objects.filter(memberships__user=request.user)
            ],
        )
    )


@auth.login_required
def accounts(request: HttpRequest) -> HttpResponse:
    return JsonResponse(
        [
            dict(id=x.id, name=x.github_account_login, profileImgUrl=x.profile_image(),)
            for x in Account.objects.filter(memberships__user=request.user)
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

# TODO: Handle installation event webhooks


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
    access_res = requests.post(
        "https://github.com/login/oauth/access_token", payload, timeout=5
    )
    try:
        access_res.raise_for_status()
    except (requests.HTTPError, requests.exceptions.Timeout):
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
        timeout=5,
    )
    try:
        user_data_res.raise_for_status()
    except (requests.HTTPError, requests.exceptions.Timeout):
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
    # TODO(chdsbd): Run this in as a background job if the user is an existing
    # user.
    try:
        user.sync_accounts()
    except SyncAccountsError:
        logger.warning("sync_accounts failed", exc_info=True)
        # ignore the errors if we were an existing user as we can use old data.
        if not existing_user:
            return Error(
                error="AccountSyncFailure",
                error_description="Failed to sync GitHub accounts for user.",
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


@csrf_exempt
@auth.login_required
@require_http_methods(["POST"])
def sync_accounts(request: HttpRequest) -> HttpResponse:
    try:
        request.user.sync_accounts()
    except SyncAccountsError:
        return JsonResponse(dict(ok=False))
    return JsonResponse(dict(ok=True))
