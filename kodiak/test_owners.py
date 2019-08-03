from pathlib import PurePosixPath

from kodiak.owners import find_owner

PATTERNS_AND_OWNERS = [
    ("*", ["@global-owner1", "@global-owner2"]),
    ("*.js", ["@js-owner"]),
    ("*.go", ["docs@example.com"]),
    ("/build/logs/", ["@doctocat"]),
    ("docs/*", ["docs@example.com"]),
    ("apps/", ["@octocat"]),
    ("/docs/", ["@doctocat"]),
]


def test_owners(code_owners: str) -> None:
    owners = find_owner(PATTERNS_AND_OWNERS, PurePosixPath("backend/core/views.go"))
    assert owners == ["docs@example.com"]
