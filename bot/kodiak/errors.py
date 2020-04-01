from typing import Optional


class RetryForSkippableChecks(Exception):
    pass


class PollForever(Exception):
    pass


class ApiCallException(Exception):
    def __init__(self, method: str, description: Optional[str] = None) -> None:
        self.method = method
        self.description = description
