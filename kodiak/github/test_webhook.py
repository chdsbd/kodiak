import pytest
import typing
from pathlib import Path
import json

from kodiak.github import Webhook, events
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

    res = client.post(
        "/api/github/hook",
        json=pull_request_event,
        headers={"X-Github-Event": "pull_request"},
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
