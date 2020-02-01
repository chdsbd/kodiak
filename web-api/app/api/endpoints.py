from fastapi import APIRouter, HTTPException
from starlette.responses import Response, PlainTextResponse, RedirectResponse
from app.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    KODIAK_API_AUTH_REDIRECT_URL,
    KODIAK_WEB_AUTHED_LANDING_PATH,
)
from starlette.requests import Request
import requests_async as http
from urllib.parse import parse_qs
from yarl import URL


api_router = APIRouter()


def get_auth_url() -> str:
    return str(
        URL("https://github.com/login/oauth/authorize").with_query(
            dict(
                client_id=str(GITHUB_CLIENT_ID),
                redirect_uri=str(KODIAK_API_AUTH_REDIRECT_URL),
            )
        )
    )


@api_router.get("/login")
def login() -> Response:
    """
    Entry point to oauth flow.

    We keep this as a simple endpoint on the API to redirect users to from the
    frontend. This way we keep complexity within the API.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#1-request-a-users-github-identity
    """
    return RedirectResponse(get_auth_url())


# TODO: handle deauthorization webhook
# https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#handling-a-revoked-github-app-authorization


@api_router.get("/auth-callback")
async def auth_callback(request: Request) -> Response:
    """
    OAuth callback handler from GitHub.

    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    code = request.query_params.get("code")
    if code is None:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    payload = dict(
        client_id=GITHUB_CLIENT_ID, client_secret=GITHUB_CLIENT_SECRET, code=code
    )
    res = await http.post("https://github.com/login/oauth/access_token", payload)
    query_string = parse_qs(res.text)
    access_token = query_string["access_token"][0]
    token_type = query_string["token_type"][0]
    res = await http.get(
        "https://api.github.com/user",
        headers=dict(authorization=f"Bearer {access_token}"),
    )
    login = res.json()["login"]
    account_id = res.json()["id"]
    print(res.json())
    print(access_token)
    # TODO: Store access token for API use.
    return RedirectResponse(KODIAK_WEB_AUTHED_LANDING_PATH)
