import json
from pathlib import Path
from typing import Tuple

import pytest
from pytest_mock import MockFixture
from starlette import status
from starlette.testclient import TestClient

from kodiak import app_config as conf
from kodiak.main import app
from kodiak.test_events import MAPPING
from kodiak.test_utils import wrap_future


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def get_body_and_hash(data: dict) -> Tuple[bytes, str]:
    import hmac
    import hashlib

    import ujson

    body = ujson.dumps(data).encode()
    sha = hmac.new(
        key=conf.SECRET_KEY.encode(), msg=body, digestmod=hashlib.sha1
    ).hexdigest()
    return body, sha


@pytest.mark.parametrize("event_name", (event_name for event_name, _schema in MAPPING))
def test_event_parsing(
    client: TestClient, event_name: str, mocker: MockFixture
) -> None:
    """Test all of the events we have"""
    handle_webhook_event = mocker.patch(
        "kodiak.main.handle_webhook_event", return_value=wrap_future(None)
    )
    for index, fixture_path in enumerate(
        (Path(__file__).parent / "test" / "fixtures" / "events" / event_name).rglob(
            "*.json"
        )
    ):
        data = json.loads(fixture_path.read_bytes())

        body, sha = get_body_and_hash(data)

        assert handle_webhook_event.call_count == index
        res = client.post(
            "/api/github/hook",
            data=body,
            headers={"X-Github-Event": event_name, "X-Hub-Signature": sha},
        )
        assert res.status_code == status.HTTP_200_OK
        assert handle_webhook_event.call_count == index + 1


def test_event_parsing_missing_github_event(
    client: TestClient, mocker: MockFixture
) -> None:
    handle_webhook_event = mocker.patch(
        "kodiak.main.handle_webhook_event", return_value=wrap_future(None)
    )
    data = {"hello": 123}

    body, sha = get_body_and_hash(data)

    assert handle_webhook_event.called is False
    res = client.post("/api/github/hook", data=body, headers={"X-Hub-Signature": sha})
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert handle_webhook_event.called is False


def test_event_parsing_invalid_signature(
    client: TestClient, mocker: MockFixture
) -> None:
    handle_webhook_event = mocker.patch(
        "kodiak.main.handle_webhook_event", return_value=wrap_future(None)
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
