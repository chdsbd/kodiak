import databases
from starlette.config import Config

config = Config(".env")

REDIS_URL = config("REDIS_URL", cast=databases.DatabaseURL, default=None) or config(
    "REDISCLOUD_URL", cast=databases.DatabaseURL
)
SECRET_KEY = config("SECRET_KEY")
GITHUB_APP_ID = config("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_PATH = config("GITHUB_PRIVATE_KEY_PATH", default=None)
GITHUB_PRIVATE_KEY = config("GITHUB_PRIVATE_KEY", default=None)
# TODO(chdsbd): Remove this old configuration option
GITHUB_TOKEN = config("GITHUB_TOKEN", default=None)


if GITHUB_PRIVATE_KEY_PATH is None and GITHUB_PRIVATE_KEY is None:
    raise ValueError("Either GITHUB_PRIVATE_KEY_PATH or GITHUB_PRIVATE_KEY must be set")
