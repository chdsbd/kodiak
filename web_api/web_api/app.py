from typing import Any, Optional, cast
from urllib.parse import parse_qs

import requests
from flask import Flask, jsonify, redirect, request
from flask_login import LoginManager, current_user, login_required, login_user
from flask_migrate import Migrate
from sqlalchemy.exc import DatabaseError
from yarl import URL

from web_api.config import create_app, login_manager
from web_api.models import User, db

app = create_app()


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    try:
        return cast(User, db.session.query(User).get(user_id))
    except DatabaseError:
        return None


@app.route("/")
def root() -> Any:
    return "Hello"


@app.route("/v1/installations")
@login_required
def installations() -> Any:
    return jsonify([])


@app.route("/v1/me")
@login_required
def me() -> Any:
    return {
        "id": current_user.id,
        "github_login": current_user.github_login,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }


@app.route("/v1/login")
def login() -> Any:
    """
    Entry point to oauth flow.

    We keep this as a simple endpoint on the API to redirect users to from the
    frontend. This way we keep complexity within the API.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#1-request-a-users-github-identity
    """
    github_oauth_url = str(
        URL("https://github.com/login/oauth/authorize").with_query(
            dict(
                client_id=app.config["GITHUB_CLIENT_ID"],
                redirect_uri=app.config["KODIAK_API_AUTH_REDIRECT_URL"],
            )
        )
    )
    return redirect(github_oauth_url)


# TODO: handle deauthorization webhook
# https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#handling-a-revoked-github-app-authorization


@app.route("/v1/auth-callback")
def auth_callback() -> Any:
    """
    OAuth callback handler from GitHub.

    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    code = request.args.get("code")
    if code is None:
        raise Exception("Missing code parameter")
    payload = dict(
        client_id=app.config["GITHUB_CLIENT_ID"],
        client_secret=app.config["GITHUB_CLIENT_SECRET"],
        code=code,
    )
    access_res = requests.post("https://github.com/login/oauth/access_token", payload)
    assert access_res.ok
    query_string = parse_qs(access_res.text)
    assert query_string.get("error") is None
    access_token = query_string["access_token"][0]
    user_res = requests.get(
        "https://api.github.com/user",
        headers=dict(authorization=f"Bearer {access_token}"),
    )
    login = user_res.json()["login"]
    account_id = int(user_res.json()["id"])

    existing_user = db.session.query(User).filter(User.github_id == account_id).first()
    if existing_user:
        existing_user.github_login = login
        existing_user.github_access_token = access_token
        user = existing_user
    else:
        user = User(
            github_id=account_id, github_login=login, github_access_token=access_token
        )
        db.session.add(user)
    db.session.commit()

    login_user(user)
    return redirect(app.config["KODIAK_WEB_AUTHED_LANDING_PATH"])
