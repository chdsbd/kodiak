#!/usr/bin/env python3
import datetime
import logging
import os
import sys
import time
from typing import Optional

import django
from django.utils.timezone import make_aware

# fmt: off
# must setup django before importing models
os.environ["DJANGO_SETTINGS_MODULE"] = "web_api.settings"
django.setup()
# pylint: disable=wrong-import-position
from core.models import UserPullRequestActivity # noqa:E402 isort:skip
# fmt: on

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def main() -> None:
    UserPullRequestActivity.generate()


if __name__ == "__main__":
    main()
