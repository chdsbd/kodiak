from __future__ import annotations

import logging
import sys
from typing import Optional

import sentry_sdk
import structlog
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sentry_sdk.integrations.logging import LoggingIntegration

from kodiak import app_config as conf
from kodiak import queries
from kodiak.github import Webhook, events
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

webhook = Webhook(app)
logger = structlog.get_logger()


redis_webhook_queue = RedisWebhookQueue()


@app.get("/")
async def root() -> str:
    return "OK"


@webhook()
async def pr_event(pr: events.PullRequestEvent) -> None:
    """
    Trigger evaluation of modified PR.
    """
    assert pr.installation is not None
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=pr.repository.owner.login,
            repo_name=pr.repository.name,
            pull_request_number=pr.number,
            installation_id=str(pr.installation.id),
        )
    )


@webhook()
async def check_run(check_run_event: events.CheckRunEvent) -> None:
    """
    Trigger evaluation of all PRs included in check run.
    """
    assert check_run_event.installation
    # Prevent an infinite loop when we update our check run
    if check_run_event.check_run.name == queries.CHECK_RUN_NAME:
        return
    for pr in check_run_event.check_run.pull_requests:
        await redis_webhook_queue.enqueue(
            event=WebhookEvent(
                repo_owner=check_run_event.repository.owner.login,
                repo_name=check_run_event.repository.name,
                pull_request_number=pr.number,
                installation_id=str(check_run_event.installation.id),
            )
        )


@webhook()
async def status_event(status_event: events.StatusEvent) -> None:
    """
    Trigger evaluation of all PRs associated with the status event commit SHA.
    """
    assert status_event.installation
    sha = status_event.commit.sha
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    async with Client(
        owner=owner, repo=repo, installation_id=installation_id
    ) as api_client:
        prs = await api_client.get_pull_requests_for_sha(sha=sha)
        if prs is None:
            logger.warning("problem finding prs for sha")
            return None
        for pr in prs:
            await redis_webhook_queue.enqueue(
                event=WebhookEvent(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    installation_id=str(installation_id),
                )
            )


@webhook()
async def pr_review(review: events.PullRequestReviewEvent) -> None:
    """
    Trigger evaluation of the modified PR.
    """
    assert review.installation
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=review.repository.owner.login,
            repo_name=review.repository.name,
            pull_request_number=review.pull_request.number,
            installation_id=str(review.installation.id),
        )
    )


def get_branch_name(raw_ref: str) -> Optional[str]:
    """
    Extract the branch name from the ref
    """
    if raw_ref.startswith("refs/heads/"):
        return raw_ref.split("refs/heads/", 1)[1]
    return None


@webhook()
async def push(push_event: events.PushEvent) -> None:
    """
    Trigger evaluation of PRs that depend on the pushed branch.
    """
    owner = push_event.repository.owner.login
    repo = push_event.repository.name
    assert push_event.installation
    installation_id = str(push_event.installation.id)
    branch_name = get_branch_name(push_event.ref)
    if branch_name is None:
        logger.info("could not extract branch name from ref", ref=push_event.ref)
        return
    async with Client(
        owner=owner, repo=repo, installation_id=installation_id
    ) as api_client:
        # find all the PRs that depend on the branch affected by this push and
        # queue them for evaluation.
        # Any PR that has a base ref matching our event ref is dependent.
        prs = await api_client.get_open_pull_requests(base=branch_name)
        for pr in prs:
            await redis_webhook_queue.enqueue(
                event=WebhookEvent(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    installation_id=installation_id,
                )
            )


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()
