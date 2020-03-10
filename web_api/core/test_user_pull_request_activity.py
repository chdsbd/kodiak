import datetime
import json
from pathlib import Path

import pytest
from django.utils.timezone import make_aware

from core.models import (
    GitHubEvent,
    UserPullRequestActivity,
    UserPullRequestActivityProgress,
)
from core.user_activity_aggregator import main as generate_user_activity

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def pull_request_kodiak_updated() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_kodiak_updated.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))
    event.save()


@pytest.fixture
def pull_request_total_opened() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_total_opened.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))
    event.save()


@pytest.fixture
def pull_request_kodiak_updated_different_institution() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load(
            (FIXTURES / "pull_request_kodiak_updated_different_institution.json").open()
        ),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))
    event.save()


@pytest.fixture
def pull_request_total_opened_different_institution() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load(
            (FIXTURES / "pull_request_total_opened_different_institution.json").open()
        ),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))
    event.save()


@pytest.mark.django_db
def test_generate(
    pull_request_total_opened: object,
    pull_request_kodiak_updated: object,
    pull_request_kodiak_updated_different_institution: object,
    pull_request_total_opened_different_institution: object,
) -> None:
    assert UserPullRequestActivityProgress.objects.count() == 0

    generate_user_activity()

    assert UserPullRequestActivity.objects.count() == 4
    assert (
        UserPullRequestActivity.objects.filter(github_installation_id=848733).count()
        == 2
    )
    assert (
        UserPullRequestActivity.objects.filter(github_installation_id=548321).count()
        == 2
    )
    assert UserPullRequestActivityProgress.objects.count() == 1


@pytest.mark.django_db
def test_generate_with_conflict(
    pull_request_total_opened: object,
    pull_request_kodiak_updated: object,
    pull_request_kodiak_updated_different_institution: object,
    pull_request_total_opened_different_institution: object,
) -> None:
    """
    If we have a conflict with an existing row we should leave the row and do
    nothing. A user can only be active once per day, so if we've already created
    an activity event for the day, that's all we can do.
    """
    assert UserPullRequestActivityProgress.objects.count() == 0

    generate_user_activity()

    assert UserPullRequestActivity.objects.count() == 4
    assert (
        UserPullRequestActivity.objects.filter(github_installation_id=848733).count()
        == 2
    )
    assert (
        UserPullRequestActivity.objects.filter(github_installation_id=548321).count()
        == 2
    )
    assert UserPullRequestActivityProgress.objects.count() == 1
    UserPullRequestActivityProgress.objects.all().delete()
    generate_user_activity()


@pytest.mark.django_db
def test_generate_min_progress(
    pull_request_total_opened: object,
    pull_request_kodiak_updated: object,
    pull_request_kodiak_updated_different_institution: object,
    pull_request_total_opened_different_institution: object,
) -> None:
    UserPullRequestActivityProgress.objects.create(
        min_date=make_aware(datetime.datetime(2050, 4, 23))
    )
    generate_user_activity()
    assert UserPullRequestActivityProgress.objects.count() == 2
    assert UserPullRequestActivity.objects.count() == 0
