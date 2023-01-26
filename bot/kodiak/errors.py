class RetryForSkippableChecks(Exception):  # noqa: N818
    pass


class PollForever(Exception):  # noqa: N818
    pass


class ApiCallException(Exception):  # noqa: N818
    def __init__(self, method: str, http_status_code: int, response: bytes) -> None:
        self.method = method
        self.status_code = http_status_code
        self.response = response


class GitHubApiInternalServerError(Exception):
    pass
