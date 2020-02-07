import os
from typing import List

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "gjzyca8n8$gg^d9u-ts6x5_+=)x*h!=ae&y$%m*ecsjly&*8j3"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS: List[str] = ["*"]


# Application definition

INSTALLED_APPS = ["django.contrib.sessions", "core"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
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

# ignore ssl issues
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Configuration for App
KODIAK_API_GITHUB_CLIENT_ID = os.environ["KODIAK_API_GITHUB_CLIENT_ID"]
KODIAK_API_GITHUB_CLIENT_SECRET = os.environ["KODIAK_API_GITHUB_CLIENT_SECRET"]
KODIAK_API_ROOT_URL = os.environ["KODIAK_API_ROOT_URL"]
