from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from kodiak.dependencies import dep_versions_from_pr


@dataclass
class FakePR:
    title: str
    body: str


def generate_test_cases() -> Iterator[tuple[FakePR, str]]:
    """
    Generate test cases from the renovate_pull_requests/ directory.

    Each example file name has the update type. For example,
    (update-major-single_pr.txt) would be a major update.

    The first line of the file is the PR title. The remainder is the body.
    """
    update_type_regex = re.compile("^update-(?P<update_type>.*)-.*.txt$")
    renovate_examples = (
        Path(__file__).parent.parent / "dependencies" / "pull_requests"
    )

    for file_name in renovate_examples.glob("*"):
        match = update_type_regex.match(file_name.name)
        assert match is not None
        update_type = match.groupdict()["update_type"]
        title, *rest = file_name.read_text().splitlines()
        body = "\n".join(rest)
        yield FakePR(title, body), update_type


@pytest.mark.parametrize("pr,update_type", generate_test_cases())
def test_merge_renovate(pr: FakePR, update_type: str) -> None:
    assert dep_versions_from_pr(pr) == update_type
