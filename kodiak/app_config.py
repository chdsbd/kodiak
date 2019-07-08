from pathlib import Path

import databases
from starlette.config import Config

config = Config(".env")

REDIS_URL = config("REDIS_URL", cast=databases.DatabaseURL, default=None) or config(
    "REDISCLOUD_URL", cast=databases.DatabaseURL
)
REDIS_POOL_SIZE = config("REDIS_POOL_SIZE", cast=int, default=20)
SECRET_KEY = config("SECRET_KEY")
GITHUB_APP_ID = config("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default=None)
GITHUB_PRIVATE_KEY = config("GITHUB_PRIVATE_KEY", default=None)


if GITHUB_PRIVATE_KEY_PATH is None and GITHUB_PRIVATE_KEY is None:
    raise ValueError("Either GITHUB_PRIVATE_KEY_PATH or GITHUB_PRIVATE_KEY must be set")


PRIVATE_KEY = (
    Path(GITHUB_PRIVATE_KEY_PATH).read_text()
    if GITHUB_PRIVATE_KEY_PATH is not None
    else GITHUB_PRIVATE_KEY
)
