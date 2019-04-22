import pytest
import typing

from kodiak.github import Webhook, events
from fastapi import FastAPI


@pytest.fixture
def webhook():
    app = FastAPI()
    return Webhook(app)


def test_correct_case(webhook: Webhook):
    """
    Passing one arg with a valid type should be accepted
    """

    @webhook()
    def push(data: events.PullRequest):
        pass

    assert webhook.event_mapping[events.PullRequest] == [push]
    assert len(webhook.event_mapping) == 1


def test_union(webhook: Webhook):
    """
    We should be able to request a union of events
    """

    @webhook()
    def push(data: typing.Union[events.PullRequest, events.Push]):
        pass

    for event in (events.PullRequest, events.Push):
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
        def push(pull: events.PullRequest, push: events.Push):
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
        def push(event: typing.Union[events.PullRequest, int]):
            pass
