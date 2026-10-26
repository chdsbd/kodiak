from __future__ import annotations

import ssl

from httpx import (
    AsyncClient,
    HTTPError,
    HTTPStatusError,
    Limits,
    Request,
    Response,
)
from httpx._config import DEFAULT_LIMITS, DEFAULT_TIMEOUT_CONFIG
from httpx._types import TimeoutTypes

__all__ = [
    "HTTPError",
    "HTTPStatusError",
    "HttpClient",
    "Limits",
    "Request",
    "Response",
]

# NOTE: this has a cost to create so we may want to set this lazily on the first HttpClient creation
context = ssl.create_default_context()


class HttpClient(AsyncClient):
    """
    HTTP Client with the SSL config cached at the module level to avoid perf issues.
    see: https://github.com/encode/httpx/issues/838
    """

    def __init__(
        self,
        *,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
        limits: Limits = DEFAULT_LIMITS,
    ):
        super().__init__(
            verify=context,
            timeout=timeout,
            limits=limits,
        )
