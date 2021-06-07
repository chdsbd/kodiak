from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, Tuple

import asyncio_redis
import pytest
from httpx import AsyncClient, Request, Response
from pytest_mock import MockFixture
from starlette import status
from starlette.testclient import TestClient

from kodiak import app_config as conf
from kodiak.main import app
from kodiak.queue import (
    INCOMING_QUEUE_NAME,
    WebhookEvent,
    process_raw_webhook_event_consumer,
)
from kodiak.test_events import MAPPING
from kodiak.test_utils import wrap_future
from kodiak.tests.fixtures import FakeThottler


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
async def redis() -> AsyncIterator[asyncio_redis.Pool]:
    redis = await asyncio_redis.Pool.create()
    yield redis
    redis.close()


@pytest.fixture(scope="module")
def event_loop() -> Iterator[object]:
    """
    Fixes some pytest issues related to which event loop it should be using.
    see: https://github.com/encode/starlette/issues/652#issuecomment-569327566
    """
    yield asyncio.get_event_loop()


def get_body_and_hash(data: Dict[str, Any]) -> Tuple[bytes, str]:
    body = json.dumps(data).encode()
    sha = hmac.new(
        key=conf.SECRET_KEY.encode(), msg=body, digestmod=hashlib.sha1
    ).hexdigest()
    return body, sha


@dataclass
class FakeWebhookQueue:
    enqueue_call_count: int = 0

    async def enqueue(self, *, event: WebhookEvent) -> None:
        self.enqueue_call_count += 1

    async def enqueue_for_repo(self, *, event: WebhookEvent, first: bool) -> int | None:
        raise NotImplementedError


@pytest.mark.parametrize("event_name", (event_name for event_name, _schema in MAPPING))
@pytest.mark.asyncio
async def test_webhook_event_can_be_enqued_and_processed(
    event_name: str, redis: asyncio_redis.Pool, mocker: MockFixture
) -> None:
    """
    Smoke test to ensure all the events types work from the HTTP server to the
    queue and back off the queue.
    """
    mocker.patch(
        "kodiak.queries.http.AsyncClient.get",
        return_value=wrap_future(
            Response(status_code=200, json=[], request=Request(method="GET", url=""))
        ),
    )
    mocker.patch(
        "kodiak.queries.get_thottler_for_installation", return_value=FakeThottler()
    )
    mocker.patch("kodiak.queries.get_token_for_install", return_value=wrap_future(str))

    for fixture_path in (
        Path(__file__).parent / "test" / "fixtures" / "events" / event_name
    ).rglob("*.json"):
        await redis.delete([INCOMING_QUEUE_NAME])
        data = json.loads(fixture_path.read_bytes())
        body, sha = get_body_and_hash(data)
        assert await redis.llen(INCOMING_QUEUE_NAME) == 0
        async with AsyncClient(app=app, base_url="http://test") as client:
            res = await client.post(
                "/api/github/hook",
                content=body,
                headers={"X-Github-Event": event_name, "X-Hub-Signature": sha},
            )
        assert res.status_code == status.HTTP_200_OK
        assert await redis.llen(INCOMING_QUEUE_NAME) == 1
        fake_webhook_queue = FakeWebhookQueue()

        await process_raw_webhook_event_consumer(
            queue=fake_webhook_queue, connection=redis
        )

        assert await redis.llen(INCOMING_QUEUE_NAME) == 0


def test_webhook_event_missing_github_event(
    client: TestClient, mocker: MockFixture
) -> None:
    handle_webhook_event = mocker.patch(
        "kodiak.main.enqueue_incoming_webhook", return_value=wrap_future(None)
    )
    data = {"hello": 123}

    body, sha = get_body_and_hash(data)

    assert handle_webhook_event.called is False
    res = client.post("/api/github/hook", data=body, headers={"X-Hub-Signature": sha})
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert handle_webhook_event.called is False


def test_webhook_event_invalid_signature(
    client: TestClient, mocker: MockFixture
) -> None:
    handle_webhook_event = mocker.patch(
        "kodiak.main.enqueue_incoming_webhook", return_value=wrap_future(None)
    )
    data = {"hello": 123}

    # use a different dict for the signature so we get an signature mismatch
    _, sha = get_body_and_hash({})

    assert handle_webhook_event.called is False
    res = client.post(
        "/api/github/hook",
        json=data,
        headers={"X-Github-Event": "content_reference", "X-Hub-Signature": sha},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert handle_webhook_event.called is False
