from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from pytest_mock import MockFixture
from starlette import status
from starlette.testclient import TestClient

from kodiak import app_config as conf
from kodiak.entrypoints.ingest import app
from kodiak.test_events import MAPPING


def test_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b"OK"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def get_body_and_hash(data: Dict[str, Any]) -> Tuple[bytes, str]:
    body = json.dumps(data).encode()
    sha = hmac.new(
        key=conf.SECRET_KEY.encode(), msg=body, digestmod=hashlib.sha1
    ).hexdigest()
    return body, sha


class FakeRedis:
    def __init__(self) -> None:
        self.called_rpush_cnt = 0
        self.called_ltrim_cnt = 0
        self.called_sadd_cnt = 0
        self.called_publish_cnt = 0

    async def rpush(self, key: str, events: list[object]) -> None:
        self.called_rpush_cnt += 1

    async def ltrim(self, key: str, start: int, end: int) -> None:
        self.called_ltrim_cnt += 1

    async def sadd(self, key: str, values: list[str]) -> None:
        self.called_sadd_cnt += 1

    async def publish(self, channel: str, message: str) -> None:
        self.called_publish_cnt += 1


@pytest.mark.parametrize("event_name", (event_name for event_name, _schema in MAPPING))
def test_webhook_event(
    client: TestClient, event_name: str, mocker: MockFixture
) -> None:
    """Test all of the events we have"""
    fake_redis = FakeRedis()
    mocker.patch("kodiak.entrypoints.ingest.redis_bot", fake_redis)
    for index, fixture_path in enumerate(
        (Path(__file__).parent / "test" / "fixtures" / "events" / event_name).rglob(
            "*.json"
        )
    ):
        data = json.loads(fixture_path.read_bytes())

        body, sha = get_body_and_hash(data)

        assert fake_redis.called_rpush_cnt == index
        res = client.post(
            "/api/github/hook",
            data=body,
            headers={"X-Github-Event": event_name, "X-Hub-Signature": sha},
        )
        assert res.status_code == status.HTTP_200_OK
        assert fake_redis.called_rpush_cnt == index + 1

    assert fake_redis.called_rpush_cnt == fake_redis.called_ltrim_cnt


def test_webhook_event_missing_github_event(
    client: TestClient, mocker: MockFixture
) -> None:
    fake_redis = FakeRedis()
    mocker.patch("kodiak.entrypoints.ingest.redis_bot", fake_redis)
    data = {"hello": 123}

    body, sha = get_body_and_hash(data)

    assert fake_redis.called_rpush_cnt == 0
    res = client.post("/api/github/hook", data=body, headers={"X-Hub-Signature": sha})
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert fake_redis.called_rpush_cnt == 0


def test_webhook_event_invalid_signature(
    client: TestClient, mocker: MockFixture
) -> None:
    fake_redis = FakeRedis()
    mocker.patch("kodiak.entrypoints.ingest.redis_bot", fake_redis)
    data = {"hello": 123}

    # use a different dict for the signature so we get an signature mismatch
    _, sha = get_body_and_hash({})

    assert fake_redis.called_rpush_cnt == 0
    res = client.post(
        "/api/github/hook",
        json=data,
        headers={"X-Github-Event": "content_reference", "X-Hub-Signature": sha},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert fake_redis.called_rpush_cnt == 0
