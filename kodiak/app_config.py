import base64
from pathlib import Path

import databases
from starlette.config import Config

from kodiak.logging import get_logging_level

config = Config(".env")

REDIS_URL = config("REDIS_URL", cast=databases.DatabaseURL, default=None) or config(
    "REDISCLOUD_URL", cast=databases.DatabaseURL
)
REDIS_POOL_SIZE = config("REDIS_POOL_SIZE", cast=int, default=20)
SECRET_KEY = config("SECRET_KEY")
GITHUB_APP_ID = config("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY = config("GITHUB_PRIVATE_KEY", default=None)
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default=None)
GITHUB_PRIVATE_KEY_BASE64 = config("GITHUB_PRIVATE_KEY", default=None)
LOGGING_LEVEL = get_logging_level(config("LOGGING_LEVEL", default="INFO"))


if GITHUB_PRIVATE_KEY is not None:
    PRIVATE_KEY = Path(GITHUB_PRIVATE_KEY_PATH).read_text()
elif GITHUB_PRIVATE_KEY is not None:
    PRIVATE_KEY = GITHUB_PRIVATE_KEY
elif GITHUB_PRIVATE_KEY_BASE64 is not None:
    PRIVATE_KEY = base64.decodebytes(GITHUB_PRIVATE_KEY_BASE64.encode()).decode()
else:
    raise ValueError(
        "Either GITHUB_PRIVATE_KEY_PATH, GITHUB_PRIVATE_KEY, or GITHUB_PRIVATE_KEY_BASE64 must be set"
    )
