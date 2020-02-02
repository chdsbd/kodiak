from starlette.config import Config
from starlette.datastructures import URL, Secret

config = Config(".env")

SECRET_KEY = config("SECRET_KEY", cast=Secret)
DATABASE_URL = config("DATABASE_URL", cast=URL)

SENTRY_DSN = config("SENTRY_DSN")
GITHUB_CLIENT_ID = config("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = config("GITHUB_CLIENT_SECRET")
KODIAK_API_AUTH_REDIRECT_URL = config("KODIAK_API_AUTH_REDIRECT_URL", cast=URL)
KODIAK_WEB_AUTHED_LANDING_PATH = config("KODIAK_WEB_AUTHED_LANDING_PATH", cast=URL)
