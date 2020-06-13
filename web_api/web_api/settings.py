import os
from typing import List

import dj_database_url
import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.django import DjangoIntegration
from yarl import URL

load_dotenv()


sentry_sdk.init(integrations=[DjangoIntegration()], send_default_pii=True)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG")

if DEBUG:
    # SECURITY WARNING: keep the secret key used in production secret!
    SECRET_KEY = "gjzyca8n8$gg^d9u-ts6x5_+=)x*h!=ae&y$%m*ecsjly&*8j3"
else:
    SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS: List[str] = ["*"]


# Application definition

INSTALLED_APPS = ["django.contrib.sessions", "core"]

MIDDLEWARE = [
    "core.middleware.HealthCheckMiddleware",
    "core.middleware.ExceptionMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "web_api.urls"

WSGI_APPLICATION = "web_api.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)
}


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": 'level=%(levelname)s msg="%(message)s" name=%(name)s '
            'pathname="%(pathname)s" lineno=%(lineno)s funcname=%(funcName)s '
            "process=%(process)d thread=%(thread)d "
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    # you can also shortcut 'loggers' and just configure logging for EVERYTHING at once
    "root": {"handlers": ["console",], "level": "INFO"},
}

# we terminate SSL at the proxy server
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# improve security for sessions to prevent interception
if not DEBUG:
    SESSION_COOKIE_SECURE = True

# Configuration for App
KODIAK_API_GITHUB_CLIENT_ID = os.environ["KODIAK_API_GITHUB_CLIENT_ID"]
KODIAK_API_GITHUB_CLIENT_SECRET = os.environ["KODIAK_API_GITHUB_CLIENT_SECRET"]
KODIAK_WEB_APP_URL = os.environ["KODIAK_WEB_APP_URL"]
KODIAK_WEB_AUTHED_LANDING_PATH = str(URL(KODIAK_WEB_APP_URL).with_path("/oauth"))
REDIS_URL = os.environ["REDIS_URL"]

# Stripe Credentials https://dashboard.stripe.com/account/apikeys
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
STRIPE_PLAN_ID = os.environ["STRIPE_PLAN_ID"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
STRIPE_PUBLISHABLE_API_KEY = os.environ["STRIPE_PUBLISHABLE_API_KEY"]
