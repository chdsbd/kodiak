"""
A process for triggering reevaluation of pull requests for a given installation.
This is useful for triggering the bot to remove the paywall status check message
after a user has started a trial or subscription.

We listen for events on a Redis list. When we receive an event we look up all
the private PRs associated with that installation. We queue webhook events like
a GitHub webhook would for each pull request to trigger the bot to reevaluate
the mergeability.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import cast

import asyncio_redis
import sentry_sdk
import structlog
from asyncio_redis.connection import Connection as RedisConnection
from asyncio_redis.replies import BlockingPopReply
from httpx import AsyncClient
from pydantic import BaseModel
from sentry_sdk.integrations.logging import LoggingIntegration

from kodiak import app_config as conf
from kodiak.logging import (
    SentryProcessor,
    add_request_info_processor,
    configure_sentry_and_logging,
)
from kodiak.queries import generate_jwt, get_token_for_install
from kodiak.queue import WebhookEvent

configure_sentry_and_logging()

logger = structlog.get_logger()

# we query for both organization repositories and user repositories because we
# do not know of the installation is a user or an organization. We filter to
# private repositories only because we may not have access to all public
# repositories and we'll only be able to see private repositories we can access.
#
# The limits on repositories and pull requests are arbitrary.
QUERY = """
query ($login: String!) {
  userdata: user(login: $login) {
    repositories(first: 100, orderBy: {field: UPDATED_AT, direction: DESC}, privacy: PRIVATE) {
      nodes {
        name
        pullRequests(first: 100, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            baseRef {
              name
            }
          }
        }
      }
    }
  }
  organizationdata: organization(login: $login) {
    repositories(first: 100, orderBy: {field: UPDATED_AT, direction: DESC}, privacy: PRIVATE) {
      nodes {
        name
        pullRequests(first: 100, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            baseRef {
              name
            }
          }
        }
      }
    }
  }
}

"""


async def get_login_for_install(*, http: AsyncClient, installation_id: str) -> str:
    app_token = generate_jwt(
        private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID
    )
    res = await http.get(
        conf.v3_url(f"/app/installations/{installation_id}"),
        headers=dict(
            Accept="application/vnd.github.machine-man-preview+json",
            Authorization=f"Bearer {app_token}",
        ),
    )
    res.raise_for_status()
    return cast(str, res.json()["account"]["login"])


async def refresh_pull_requests_for_installation(
    *, installation_id: str, redis: RedisConnection
) -> None:
    async with AsyncClient() as http:
        login = await get_login_for_install(http=http, installation_id=installation_id)
        token = await get_token_for_install(
            session=http, installation_id=installation_id
        )
        res = await http.post(
            conf.GITHUB_V4_API_URL,
            json=dict(query=QUERY, variables=dict(login=login)),
            headers=dict(Authorization=f"Bearer {token}"),
        )
    res.raise_for_status()

    organizationdata = res.json()["data"]["organizationdata"]
    userdata = res.json()["data"]["userdata"]
    user_kind = None
    if organizationdata is not None:
        user_kind = "organization"
        data = organizationdata
    elif userdata is not None:
        user_kind = "user"
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
                    target_name=pull_request["baseRef"]["name"],
                    pull_request_number=pull_request["number"],
                    installation_id=installation_id,
                )
            )
    for event in events:
        await redis.zadd(
            event.get_webhook_queue_name(),
            {event.json(): time.time()},
            only_if_not_exists=True,
        )
    logger.info(
        "pull_requests_refreshed",
        installation_id=installation_id,
        events_queued=len(events),
        user_kind=user_kind,
    )


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
        try:
            res: BlockingPopReply = await redis.blpop(
                ["kodiak:refresh_pull_requests_for_installation"], timeout=5
            )
        except asyncio_redis.exceptions.TimeoutError:
            logger.info("pull_request_refresh", timeout_reached=True)
            continue
        pr_refresh_message = RefreshPullRequestsMessage.parse_raw(res.value)
        installation_id = pr_refresh_message.installation_id
        start = time.monotonic()
        await refresh_pull_requests_for_installation(
            installation_id=installation_id, redis=redis
        )
        logger.info(
            "pull_request_refresh",
            installation_id=installation_id,
            duration=time.monotonic() - start,
        )


def main() -> None:
    asyncio.run(main_async())
