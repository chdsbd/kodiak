import pytest
from pathlib import Path
from pydantic import BaseModel
import json

from kodiak.github import events


event_data = [
    (events.CheckRunEvent, "check_run_event.json"),
    (events.Ping, "ping_event.json"),
    (events.PullRequestEvent, "pull_request_event.json"),
    (events.PullRequestReviewEvent, "pull_request_review_event.json"),
    (events.StatusEvent, "status_event.json"),
    (events.PushEvent, "push_event.json"),
]


@pytest.mark.parametrize("event, file_name", event_data)
def test_event_parsing(event: BaseModel, file_name: str):
    event.parse_file(Path(__file__).parent / "fixtures" / file_name)


def test_event_count():
    assert len(event_data) == len(
        events.event_registry
    ), "ensure we're checking all registered events"
