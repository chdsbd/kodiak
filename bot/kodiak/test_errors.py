from __future__ import annotations

from typing import Any

import pytest

from kodiak import errors


@pytest.mark.parametrize(
    "response,expected",
    [
        (
            [
                {
                    "message": "Something went wrong while executing your query. Please include `904B:6354:1B60F6:57C5B5:626C9136` when reporting this issue."
                }
            ],
            {"internal"},
        ),
        (
            [
                {
                    "type": "RATE_LIMITED",
                    "message": "API rate limit exceeded for installation ID 000001.",
                }
            ],
            {"rate_limited"},
        ),
        (
            [{"message": "Some unexpected error"}],
            {"unknown"},
        ),
        (
            [
                {
                    "locations": [{"column": "3", "line": "147"}],
                    "message": "Could not resolve to a Repository with the name 'chdsbd/.github'.",
                    "path": ["orgConfigRepo"],
                    "type": "NOT_FOUND",
                }
            ],
            {"not_found"},
        ),
        (
            {},
            set(),
        ),
        (
            None,
            set(),
        ),
    ],
)
def test_identify_github_graphql_error(response: Any, expected: set[str]) -> None:
    assert errors.identify_github_graphql_error(response) == expected
