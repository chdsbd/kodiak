"""
Accept webhooks from GitHub and add them to the Redis queues.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from kodiak.redis_client import redis_bot
import structlog
import uvicorn
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette import status
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from kodiak import app_config as conf
from kodiak.entrypoints.worker import PubsubIngestQueueSchema
from kodiak.logging import configure_logging
from kodiak.queue import INGEST_QUEUE_NAMES, QUEUE_PUBSUB_INGEST, get_ingest_queue
from kodiak.schemas import RawWebhookEvent

configure_logging()

logger = structlog.get_logger()

app = Starlette()
app.add_middleware(SentryAsgiMiddleware)


@app.route("/", methods=["GET"])
async def root(_: Request) -> Response:
    return PlainTextResponse("OK")


@app.route("/api/github/hook", methods=["POST"])
async def github_webhook_event(request: Request) -> Response:
    expected_sha = hmac.new(
        key=conf.SECRET_KEY.encode(), msg=(await request.body()), digestmod=hashlib.sha1
    ).hexdigest()

    try:
        github_event = request.headers["X-Github-Event"]
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing required X-Github-Event header",
        ) from e
    try:
        hub_signature = request.headers["X-Hub-Signature"]
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing required X-Hub-Signature header",
        ) from e

    sha = hub_signature.replace("sha1=", "")
    if not hmac.compare_digest(sha, expected_sha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature: X-Hub-Signature",
        )
    event: dict[str, Any] = await request.json()

    log = logger.bind(event_name=github_event, event=event)
    installation_id: int | None = event.get("installation", {}).get("id")

    if github_event in {
        "github_app_authorization",
        "installation",
        "installation_repositories",
    }:
        log.info("administrative_event_received")
        return JSONResponse({"ok": True})

    if installation_id is None:
        log.warning("unexpected_event_skipped")
        return JSONResponse({"ok": True})

    ingest_queue = get_ingest_queue(installation_id)

    await redis_bot.rpush(
        ingest_queue,
        RawWebhookEvent(event_name=github_event, payload=event).json(),
    )

    await redis_bot.ltrim(ingest_queue, 0, conf.INGEST_QUEUE_LENGTH)
    await redis_bot.sadd(INGEST_QUEUE_NAMES, ingest_queue)
    await redis_bot.publish(
        QUEUE_PUBSUB_INGEST,
        PubsubIngestQueueSchema(installation_id=installation_id).json(),
    )
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    uvicorn.run("kodiak.entrypoints.ingest:app", host="0.0.0.0", port=conf.PORT)
