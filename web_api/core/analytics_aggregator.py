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
from core.models import GitHubEvent, PullRequestActivity, PullRequestActivityProgress # noqa:E402 isort:skip
# fmt: on

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def main() -> None:
    start_time = time.time()
    pr_progress: Optional[
        PullRequestActivityProgress
    ] = PullRequestActivityProgress.objects.order_by("min_date").first()
    if pr_progress:
        min_date = make_aware(
            datetime.datetime(
                pr_progress.min_date.year,
                pr_progress.min_date.month,
                pr_progress.min_date.day,
            )
        )
        events_aggregated = GitHubEvent.objects.filter(created_at__gte=min_date).count()
    else:
        min_date = None
        events_aggregated = GitHubEvent.objects.count()
    new_min_date = datetime.date.today()
    PullRequestActivity.generate_activity_data(min_date=min_date)
    PullRequestActivityProgress.objects.create(min_date=new_min_date)
    logger.info(
        "generate_activity_data events_aggregated=%s min_date=%s new_min_date=%s duration_seconds=%s",
        events_aggregated,
        min_date,
        new_min_date,
        time.time() - start_time,
    )


if __name__ == "__main__":
    main()
