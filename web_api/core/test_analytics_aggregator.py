import datetime
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils.timezone import make_aware

from core.models import GitHubEvent, PullRequestActivity, PullRequestActivityProgress

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def pull_request_kodiak_updated() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_kodiak_updated.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))
    event.save()


@pytest.mark.django_db
def test_analytics_aggregator(pull_request_kodiak_updated: object) -> None:
    assert PullRequestActivityProgress.objects.count() == 0
    assert PullRequestActivity.objects.count() == 0
    call_command("aggregate_pull_request_activity")
    assert PullRequestActivityProgress.objects.count() == 1
    assert PullRequestActivity.objects.count() == 1
    pull_request_activity = PullRequestActivity.objects.get()
    pull_request_activity_progress = PullRequestActivityProgress.objects.get()

    assert pull_request_activity_progress.min_date == datetime.date.today()
    assert pull_request_activity.total_opened == 0
    assert pull_request_activity.total_merged == 0
    assert pull_request_activity.total_closed == 0

    assert pull_request_activity.kodiak_approved == 0
    assert pull_request_activity.kodiak_merged == 0
    assert pull_request_activity.kodiak_updated == 1


@pytest.mark.django_db
def test_analytics_aggregator_min_date(pull_request_kodiak_updated: object) -> None:
    PullRequestActivityProgress.objects.create(min_date=datetime.date(2020, 2, 10))
    PullRequestActivityProgress.objects.create(min_date=datetime.date.today())
    assert PullRequestActivity.objects.count() == 0
    call_command("aggregate_pull_request_activity")
    assert PullRequestActivity.objects.count() == 0
