from __future__ import annotations

import sentry_sdk
import structlog
from fastapi import FastAPI
from sentry_asgi import SentryMiddleware

from kodiak import queries
from kodiak.github import Webhook, events
from kodiak.queries import close_clients, get_client_for_org
from kodiak.queue import RedisWebhookQueue, WebhookEvent

sentry_sdk.init()

app = FastAPI()
app.add_middleware(SentryMiddleware)

webhook = Webhook(app)
logger = structlog.get_logger()


redis_webhook_queue = RedisWebhookQueue()


@app.get("/")
async def root() -> str:
    return "OK"


@webhook()
async def pr_event(pr: events.PullRequestEvent) -> None:
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
    assert status_event.installation
    sha = status_event.commit.sha
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    api_client = await get_client_for_org(
        owner=owner, repo=repo, installation_id=installation_id
    )
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
    assert review.installation
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=review.repository.owner.login,
            repo_name=review.repository.name,
            pull_request_number=review.pull_request.number,
            installation_id=str(review.installation.id),
        )
    )


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_clients()
