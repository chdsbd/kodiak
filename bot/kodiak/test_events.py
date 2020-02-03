from pathlib import Path

import pytest
from pydantic import BaseModel

from kodiak import events

# A mapping of all events to their corresponding fixtures. Any new event must
# register themselves here for testing.
MAPPING = (
    ("check_run", events.CheckRunEvent),
    ("check_run", events.CheckRunEvent),
    ("pull_request", events.PullRequestEvent),
    ("pull_request_review", events.PullRequestReviewEvent),
    ("status", events.StatusEvent),
    ("push", events.PushEvent),
)


@pytest.mark.parametrize("event_name, schema", MAPPING)
def test_event_parsing(event_name: str, schema: BaseModel) -> None:
    for fixture_path in (
        Path(__file__).parent / "test" / "fixtures" / "events" / event_name
    ).rglob("*.json"):
        schema.parse_file(fixture_path)
