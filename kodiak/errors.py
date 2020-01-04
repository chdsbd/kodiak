class RetryForSkippableChecks(Exception):
    pass


class PollForever(Exception):
    pass


class ApiCallException(Exception):
    def __init__(self, method: str) -> None:
        self.method = method
