from __future__ import annotations

import hashlib
import hmac
import logging
import sys
from typing import Any, Dict, Optional, cast

import sentry_sdk
import structlog
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette import status
from starlette.requests import Request

from kodiak import app_config as conf
from kodiak.logging import (
    SentryProcessor,
    add_request_info_processor,
    configure_sentry_and_logging,
)
from kodiak.queue import handle_webhook_event, redis_webhook_queue

# disable uvicorn log handlers. We use our own that matches our JSON log formatting.
logging.getLogger("uvicorn.access").handlers = []
logging.getLogger("uvicorn.access").propagate = True
logging.getLogger("uvicorn").handlers = []

configure_sentry_and_logging()

app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)


@app.get("/")
async def root() -> str:
    return "OK"


@app.post("/api/github/hook")
async def webhook_event(
    event: Dict[str, Any],
    *,
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature: str = Header(None),
) -> None:
    """
    Verify and accept GitHub Webhook payloads.
    """
    # FastAPI allows x_github_event to be nullable and we cannot type it as
    # Optional in the function definition
    # https://github.com/tiangolo/fastapi/issues/179
    github_event = cast(Optional[str], x_github_event)
    github_signature = cast(Optional[str], x_hub_signature)
    expected_sha = hmac.new(
        key=conf.SECRET_KEY.encode(), msg=(await request.body()), digestmod=hashlib.sha1
    ).hexdigest()
    if github_event is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: X-Github-Event",
        )
    if github_signature is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required signature: X-Hub-Signature",
        )
    sha = github_signature.replace("sha1=", "")
    if not hmac.compare_digest(sha, expected_sha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature: X-Hub-Signature",
        )

    await handle_webhook_event(
        queue=redis_webhook_queue, event_name=github_event, payload=event
    )


@app.on_event("startup")
async def startup() -> None:
    await redis_webhook_queue.create()


if __name__ == "__main__":
    uvicorn.run("kodiak.main:app", host="0.0.0.0", port=conf.PORT)
