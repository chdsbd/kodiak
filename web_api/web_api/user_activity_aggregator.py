#!/usr/bin/env python3
import os

import django

# fmt: off
# must setup django before importing models
os.environ["DJANGO_SETTINGS_MODULE"] = "web_api.settings"
django.setup()
# pylint: disable=wrong-import-position
from web_api.models import UserPullRequestActivity # noqa:E402 isort:skip
# fmt: on


def main() -> None:
    UserPullRequestActivity.generate()


if __name__ == "__main__":
    main()
