from __future__ import annotations

import asyncio
import structlog
from typing import cast

import asyncio_redis
import requests_async as http
import sentry_sdk
from asyncio_redis.replies import BlockingPopReply
from pydantic import BaseModel

from kodiak import app_config as conf
from kodiak.queries import generate_jwt, get_token_for_install
from kodiak.queue import WebhookEvent, redis_webhook_queue

sentry_sdk.init()


logger = structlog.get_logger()

QUERY = """
query ($login: String!) {
  userdata: user(login: $login) {
    repositories(first: 5) {
      nodes {
        name
        pullRequests(first: 50, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
          }
        }
      }
    }
  }
  organizationdata: organization(login: $login) {
    repositories(first: 5) {
      nodes {
        name
        pullRequests(first: 50, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
          }
        }
      }
    }
  }
}

"""


async def get_login_for_install(*, installation_id: str) -> str:
    app_token = generate_jwt(
        private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID
    )
    res = await http.get(
        f"https://api.github.com/app/installations/{installation_id}",
        headers=dict(
            Accept="application/vnd.github.machine-man-preview+json",
            Authorization=f"Bearer {app_token}",
        ),
    )
    res.raise_for_status()
    return cast(str, res.json()["account"]["login"])


async def refresh_pull_requests_for_installation(*, installation_id: str) -> None:
    login = await get_login_for_install(installation_id=installation_id)
    token = get_token_for_install(installation_id=installation_id)
    res = await http.post(
        "https://api.github.com/graphql",
        json=dict(query=QUERY, variables=dict(login=login)),
        headers=dict(Authorization=f"Bearer {token}"),
    )
    res.raise_for_status()

    organizationdata = res.json()["data"]["organizationdata"]
    userdata = res.json()["data"]["userdata"]
    if organizationdata is not None:
        data = organizationdata
    elif userdata is not None:
        data = userdata
    else:
        raise ValueError("missing data for user/organization")

    events = []
    for repository in data["repositories"]["nodes"]:
        repo_name = repository["name"]
        for pull_request in repository["pullRequests"]["nodes"]:
            events.append(
                WebhookEvent(
                    repo_owner=login,
                    repo_name=repo_name,
                    pull_request_number=pull_request["number"],
                    installation_id=installation_id,
                )
            )
    logger.info("queuing %s events", len(events))
    for event in events:
        await redis_webhook_queue.enqueue(event=event)


class RefreshPullRequestsMessage(BaseModel):
    installation_id: str


async def main_async() -> None:
    redis_db = 0
    try:
        redis_db = int(conf.REDIS_URL.database)
    except ValueError:
        pass
    redis = await asyncio_redis.Connection.create(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=conf.REDIS_URL.password or None,
        db=redis_db,
    )
    while True:
        logger.info("block for new events")
        try:
            res: BlockingPopReply = await redis.blpop(
                ["kodiak:refresh_pull_requests_for_installation"], timeout=5
            )
        except asyncio_redis.exceptions.TimeoutError:
            continue
        pr_refresh_message = RefreshPullRequestsMessage.parse_raw(res.value)
        installation_id = pr_refresh_message.installation_id
        logger.info("refreshing pull requests for", installation_id=installation_id)
        await refresh_pull_requests_for_installation(installation_id=installation_id)


def main() -> None:
    asyncio.run(main_async())
