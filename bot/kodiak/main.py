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
from sentry_sdk.integrations.logging import LoggingIntegration
from starlette import status
from starlette.requests import Request

from kodiak import app_config as conf
from kodiak.custom_log import SentryProcessor, add_request_info_processor
from kodiak.queue import handle_webhook_event, redis_webhook_queue

# for info on logging formats see: https://docs.python.org/3/library/logging.html#logrecord-attributes
logging.basicConfig(
    stream=sys.stdout,
    level=conf.LOGGING_LEVEL,
    format="%(levelname)s %(name)s:%(filename)s:%(lineno)d %(message)s",
)

# disable sentry logging middleware as the structlog processor provides more
# info via the extra data field
sentry_sdk.init(integrations=[LoggingIntegration(level=None, event_level=None)])

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
