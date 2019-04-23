import pytest
from pathlib import Path
from pydantic import BaseModel
import json

from kodiak.github import events, fixtures


@pytest.mark.parametrize("event, file_name", fixtures.MAPPING)
def test_event_parsing(event: BaseModel, file_name: str):
    event.parse_file(Path(__file__).parent / "fixtures" / file_name)


def test_event_count():
    assert len(fixtures.MAPPING) == len(
        events.event_registry
    ), "ensure we're checking all registered events"
