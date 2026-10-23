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


class InstallationTokenError(Exception):
    """
    GitHub refused to issue an access token for an installation, e.g. because
    the organization has an IP allow list enabled.
    """
