from starlette.config import Config
from starlette.datastructures import URL, Secret

config = Config()

SECRET_KEY = config("SECRET_KEY", cast=Secret)
DATABASE_URL = config('DATABASE_URL', cast=URL)
SENTRY_DSN = config("SENTRY_DSN")
