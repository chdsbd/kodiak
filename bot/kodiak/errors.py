from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from typing_extensions import Literal


class RetryForSkippableChecks(Exception):
    pass


class PollForever(Exception):
    pass


class ApiCallException(Exception):
    def __init__(self, method: str, http_status_code: int, response: bytes) -> None:
        self.method = method
        self.status_code = http_status_code
        self.response = response


class GitHubApiInternalServerError(Exception):
    pass


def identify_github_graphql_error(
    errors: Iterable[Any],
) -> set[Literal["rate_limited", "internal", "unknown"]]:
    error_kinds = set()  # type: set[Literal["rate_limited", "internal", "unknown"]]
    if not errors:
        return error_kinds
    try:
        for error in errors:
            if "type" in error and error["type"] == "RATE_LIMITED":
                error_kinds.add("rate_limited")
            elif "message" in error and error["message"].startswith(
                "Something went wrong while executing your query."
            ):
                error_kinds.add("internal")
            else:
                error_kinds.add("unknown")
    except TypeError:
        pass
    return error_kinds
