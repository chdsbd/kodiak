import base64
from pathlib import Path
from typing import Any, Optional, Type, TypeVar, overload

import databases
from starlette.config import Config, undefined
from starlette.datastructures import CommaSeparatedStrings

from kodiak.logging import get_logging_level

T = TypeVar("T")


# TODO: Remove when https://github.com/encode/starlette/pull/1732 is merged.
class TypedConfig(Config):
    @overload  # type: ignore [override]
    def __call__(self, key: str, cast: Type[T], default: T = ...) -> T:
        ...

    @overload
    def __call__(self, key: str, cast: Type[str] = ..., default: str = ...) -> str:
        ...

    @overload
    def __call__(
        self, key: str, cast: Type[str] = ..., default: None = ...
    ) -> Optional[str]:
        ...

    def __call__(
        self, key: str, cast: Optional[type] = None, default: Any = undefined
    ) -> Any:
        return super().get(key, cast=cast, default=default)


config = TypedConfig(".env")

PORT = config("PORT", cast=int, default=8000)
REDIS_URL = config("REDIS_URL", cast=databases.DatabaseURL, default=None) or config(
    "REDISCLOUD_URL", cast=databases.DatabaseURL
)
SECRET_KEY = config("SECRET_KEY")
GITHUB_APP_ID = config("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY = config("GITHUB_PRIVATE_KEY", default=None)
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default=None)
GITHUB_PRIVATE_KEY_BASE64 = config("GITHUB_PRIVATE_KEY_BASE64", default=None)
LOGGING_LEVEL = get_logging_level(config("LOGGING_LEVEL", default="INFO"))
GITHUB_APP_NAME = config("GITHUB_APP_NAME")
USAGE_REPORTING = config("USAGE_REPORTING", cast=bool, default=False)
USAGE_REPORTING_EVENTS = set(
    config(
        "USAGE_REPORTING_EVENTS",
        cast=CommaSeparatedStrings,
        default=["pull_request", "pull_request_review", "pull_request_comment"],
    )
)
USAGE_REPORTING_QUEUE_LENGTH = config(
    "USAGE_REPORTING_QUEUE_LENGTH", cast=int, default=10_000
)
INGEST_QUEUE_LENGTH = config("INGEST_QUEUE_LENGTH", cast=int, default=1_000)
REDIS_BLOCKING_POP_TIMEOUT_SEC = config(
    "REDIS_BLOCKING_POP_TIMEOUT_SEC", cast=int, default=10
)
# if we don't get a reply from Redis within a short period, we have an error because we always expect short response times from redis. We specify a timeout for blocking operations
REDIS_SOCKET_TIMEOUT_SEC = config("REDIS_SOCKET_TIMEOUT_SEC", cast=int, default=90)
# if we can't open a TCP connection quickly, we should raise a timeout.
REDIS_SOCKET_CONNECT_TIMEOUT_SEC = config(
    "REDIS_SOCKET_CONNECT_TIMEOUT_SEC", cast=int, default=30
)

SUBSCRIPTIONS_ENABLED = config("SUBSCRIPTIONS_ENABLED", cast=bool, default=False)

# For GitHub Enterprise, the v3 API root has the form:
# http(s)://[hostname]/api/v3, instead of https://api.github.com.
GITHUB_V3_API_ROOT = config("GITHUB_V3_API_ROOT", default="https://api.github.com")

# For GitHub Enterprise, the v4 API has the form:
# http(s)://[hostname]/api/graphql, instead of https://api.github.com/graphql.
GITHUB_V4_API_URL = config(
    "GITHUB_V4_API_URL", default="https://api.github.com/graphql"
)

# An extra header to send with git API requests.
GITHUB_API_HEADER_NAME = config("GITHUB_API_HEADER_NAME", default=None)
GITHUB_API_HEADER_VALUE = config("GITHUB_API_HEADER_VALUE", default=None)

if GITHUB_PRIVATE_KEY is not None:
    PRIVATE_KEY = GITHUB_PRIVATE_KEY
elif GITHUB_PRIVATE_KEY_PATH is not None:
    PRIVATE_KEY = Path(GITHUB_PRIVATE_KEY_PATH).read_text()
elif GITHUB_PRIVATE_KEY_BASE64 is not None:
    PRIVATE_KEY = base64.decodebytes(GITHUB_PRIVATE_KEY_BASE64.encode()).decode()
else:
    raise ValueError(
        "Either GITHUB_PRIVATE_KEY_PATH, GITHUB_PRIVATE_KEY, or GITHUB_PRIVATE_KEY_BASE64 must be set"
    )


def v3_url(path: str) -> str:
    return GITHUB_V3_API_ROOT + path
