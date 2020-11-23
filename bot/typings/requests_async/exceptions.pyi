from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    HTTPError,
    ReadTimeout,
    RequestException,
    Timeout,
    TooManyRedirects,
    URLRequired,
)

class ContentNotAvailable(Exception):
    pass

__all__ = [
    "ConnectionError",
    "ConnectTimeout",
    "HTTPError",
    "ReadTimeout",
    "RequestException",
    "Timeout",
    "TooManyRedirects",
    "URLRequired",
    "ContentNotAvailable",
]
