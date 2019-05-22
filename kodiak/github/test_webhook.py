import pytest
import typing
from pathlib import Path
import json
import inspect

from kodiak.github import Webhook, events, fixtures
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette import status


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture
def webhook(app: FastAPI):
    return Webhook(app)


@pytest.fixture
def client(app: FastAPI):
    return TestClient(app)


@pytest.fixture
def pull_request_event():
    file = Path(__file__).parent / "fixtures" / "pull_request_event.json"
    return json.loads(file.read_bytes())


def test_correct_case(webhook: Webhook, client: TestClient, pull_request_event):
    """
    Passing one arg with a valid type should be accepted
    """

    hook_run = False

    @webhook()
    def push(data: events.PullRequestEvent):
        nonlocal hook_run
        hook_run = True
        assert isinstance(data, events.PullRequestEvent)

    assert webhook.event_mapping[events.PullRequestEvent] == [push]
    assert len(webhook.event_mapping) == 1

    body, sha = get_body_and_hash(pull_request_event)

    res = client.post(
        "/api/github/hook",
        data=body,
        headers={"X-Github-Event": "pull_request", "X-Hub-Signature": sha},
    )
    assert res.status_code == status.HTTP_200_OK
    assert hook_run


def test_union(webhook: Webhook):
    """
    We should be able to request a union of events
    """

    @webhook()
    def push(data: typing.Union[events.PullRequestEvent, events.PushEvent]):
        pass

    for event in (events.PullRequestEvent, events.PushEvent):
        assert webhook.event_mapping[event] == [push]
    assert len(webhook.event_mapping) == 2


def too_few_args(webhook: Webhook):
    with pytest.raises(TypeError, match="invalid number of arguments"):

        @webhook()
        def push():
            pass


def test_too_many_args(webhook: Webhook):
    with pytest.raises(TypeError, match="invalid number of arguments"):

        @webhook()
        def push(pull: events.PullRequestEvent, push: events.PushEvent):
            pass


def test_invalid_arg_type(webhook: Webhook):
    with pytest.raises(
        TypeError,
        match="Invalid type annotation",
        message="we only support `github.events` types in our annotation.",
    ):

        @webhook()
        def push(event: dict):
            pass


def test_invalid_union(webhook: Webhook):
    with pytest.raises(
        TypeError,
        match="Invalid type annotation",
        message="we only support `github.events` types in our annotation.",
    ):

        @webhook()
        def push(event: typing.Union[events.PullRequestEvent, int]):
            pass


def get_body_and_hash(data: dict) -> typing.Tuple[bytes, str]:
    import hmac
    import hashlib
    import os

    import ujson

    body = ujson.dumps(data).encode()
    sha = hmac.new(
        key=os.environ["SECRET_KEY"].encode(), msg=body, digestmod=hashlib.sha1
    ).hexdigest()
    return body, sha


@pytest.mark.parametrize("event, file_name", fixtures.MAPPING)
def test_event_parsing(
    client: TestClient,
    webhook: Webhook,
    event: typing.Type[events.GithubEvent],
    file_name: str,
):
    """Test all of the events we have"""
    data = json.loads((Path(__file__).parent / "fixtures" / file_name).read_bytes())

    hook_run = 0

    def push(data: events.GithubEvent):
        nonlocal hook_run
        hook_run += 1
        assert isinstance(data, event)

    async def push_async(data: events.GithubEvent):
        nonlocal hook_run
        hook_run += 1
        assert isinstance(data, event)

    # manually configure push and push_async to listen for parameterized event
    push.__annotations__["data"] = event
    push_async.__annotations__["data"] = event
    webhook()(push)
    webhook()(push_async)

    assert webhook.event_mapping[event] == [push, push_async]
    assert len(webhook.event_mapping) == 1, "we have one event mapping to two listeners"

    body, sha = get_body_and_hash(data)

    res = client.post(
        "/api/github/hook",
        data=body,
        headers={"X-Github-Event": event._event_name, "X-Hub-Signature": sha},
    )
    assert res.status_code == status.HTTP_200_OK
    assert hook_run == 2, "push and push_async should both be called"


def test_event_count():
    """
    Verify we are testing all of the events

    If this is failing, we probably forgot to register an event in events
    """
    all_events = []
    for item in events.__dict__.values():
        if (
            inspect.isclass(item)
            and issubclass(item, events.GithubEvent)
            and item != events.GithubEvent
        ):
            all_events.append(item)

    assert set(all_events) == {
        event_class for event_class, _fixture_name in fixtures.MAPPING
    }
