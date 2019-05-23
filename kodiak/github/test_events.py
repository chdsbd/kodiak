from pathlib import Path

import pytest
from pydantic import BaseModel

from kodiak.github import events, fixtures


@pytest.mark.parametrize("event, file_name", fixtures.MAPPING)
def test_event_parsing(event: BaseModel, file_name: str) -> None:
    event.parse_file(Path(__file__).parent / "fixtures" / file_name)


def test_events() -> None:
    for fixture_path in (Path(__file__).parent / "fixtures").rglob("*/*.json"):
        event_name = fixture_path.parent.name.replace("_event", "")
        events.event_registry[event_name].parse_file(fixture_path)


def test_event_count() -> None:
    assert len({cls for cls, _fixture in fixtures.MAPPING}) == len(
        events.event_registry
    ), "ensure we're checking all registered events"


def test_event_docs() -> None:
    """
    All events should have docstrings
    """
    for doc, _ in fixtures.MAPPING:
        assert doc.__doc__ is not None
        assert "https://developer.github.com/" in doc.__doc__
