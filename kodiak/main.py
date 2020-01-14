from __future__ import annotations

import logging
import sys
from typing import List

import pydantic
import sentry_sdk
import structlog
from fastapi import FastAPI
from requests_async import HttpError
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sentry_sdk.integrations.logging import LoggingIntegration
from starlette.requests import Request

from kodiak import app_config as conf
from kodiak import auth, events, queries
from kodiak.logging import SentryProcessor, add_request_info_processor
from kodiak.queries import Client
from kodiak.queue import RedisWebhookQueue, WebhookEvent

# for info on logging formats see: https://docs.python.org/3/library/logging.html#logrecord-attributes
logging.basicConfig(
    stream=sys.stdout,
    level=conf.LOGGING_LEVEL,
    format="%(levelname)s %(name)s:%(filename)s:%(lineno)d %(message)s",
)

# disable sentry logging middleware as the structlog processor provides more
# info via the extra data field
# TODO(sbdchd): waiting on https://github.com/getsentry/sentry-python/pull/444
# to be merged & released to remove `# type: ignore`
sentry_sdk.init(
    integrations=[LoggingIntegration(level=None, event_level=None)]  # type: ignore
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_request_info_processor,
        SentryProcessor(level=logging.WARNING),
        structlog.processors.KeyValueRenderer(key_order=["event"], sort_keys=True),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)

logger = structlog.get_logger()


redis_webhook_queue = RedisWebhookQueue()


@app.get("/")
async def root() -> str:
    return "OK"


class PullRequest(pydantic.BaseModel):
    number: int


async def get_webhook_events(event_name: str, event_body: bytes) -> List[WebhookEvent]:
    log = logger.bind(event=event_name)
    if event_name == "check_run":
        check_run = events.CheckRunEvent.parse_raw(event_body)
        # Prevent an infinite loop when we update our check run
        if check_run.check_run.name == queries.CHECK_RUN_NAME:
            return []
        return [
            WebhookEvent(
                repo_owner=check_run.repository.owner.login,
                repo_name=check_run.repository.name,
                pull_request_number=pr.number,
                installation_id=str(check_run.installation.id),
            )
            for pr in check_run.check_run.pull_requests
        ]
    if event_name == "pull_request":
        pull_request = events.PullRequestEvent.parse_raw(event_body)
        return [
            WebhookEvent(
                repo_owner=pull_request.repository.owner.login,
                repo_name=pull_request.repository.name,
                pull_request_number=pull_request.number,
                installation_id=str(pull_request.installation.id),
            )
        ]
    if event_name == "pull_request_review":
        pull_request_review = events.PullRequestReviewEvent.parse_raw(event_body)
        return [
            WebhookEvent(
                repo_owner=pull_request_review.repository.owner.login,
                repo_name=pull_request_review.repository.name,
                pull_request_number=pull_request_review.pull_request.number,
                installation_id=str(pull_request_review.installation.id),
            )
        ]
    if event_name == "status":
        status_event = events.StatusEvent.parse_raw(event_body)
        sha = status_event.commit.sha
        owner = status_event.repository.owner.login
        repo = status_event.repository.name
        installation_id = str(status_event.installation.id)
        async with Client(
            owner=owner, repo=repo, installation_id=installation_id
        ) as api_client:
            res = await api_client.get_pull_requests_for_sha(sha=sha)
        try:
            res.raise_for_status()
        except HttpError:
            log.warning("problem finding pull requests for sha", exc_info=True)
            return []

        return [
            WebhookEvent(
                repo_owner=owner,
                repo_name=repo,
                pull_request_number=pr.number,
                installation_id=installation_id,
            )
            for pr in (PullRequest.parse_obj(pr) for pr in res.json())
        ]

    log.info("no handler for event")
    return []


@app.post("/api/github/hook")
async def webhook(request: Request) -> None:
    x_github_event = request.headers.get("X-Github-Event")
    x_hub_signature = request.headers.get("X-Hub-Signature")
    event_body = await request.body()
    github_event = await auth.extract_github_event(
        body=event_body, x_github_event=x_github_event, x_hub_signature=x_hub_signature
    )
    webhook_events = await get_webhook_events(
        event_name=github_event, event_body=event_body
    )

    for event in webhook_events:
        await redis_webhook_queue.enqueue(event=event)


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()
