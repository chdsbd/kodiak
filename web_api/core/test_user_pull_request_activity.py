import datetime
import json
from pathlib import Path

import pytest
from django.utils import timezone
from django.utils.timezone import make_aware

from core.models import (
    Account,
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


def create_user_activity(
    *, account: Account, user_id: int, pr_number: int, date: datetime.date
) -> None:
    repo_name = "acme_web"
    UserPullRequestActivity.objects.create(
        github_installation_id=account.github_installation_id,
        github_repository_name=repo_name,
        github_pull_request_number=pr_number,
        github_user_login=f"acme-user-{user_id}",
        github_user_id=user_id,
        is_private_repository=True,
        activity_date=date,
        opened_pull_request=True,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=account.github_installation_id,
        github_repository_name=repo_name,
        github_pull_request_number=pr_number,
        github_user_login="kodiak[bot]",
        github_user_id=0,
        is_private_repository=True,
        activity_date=date,
        opened_pull_request=True,
    )


@pytest.mark.django_db
def test_get_active_users_in_last_30_days() -> None:
    account = Account(github_installation_id=52324234)
    create_user_activity(
        account=account,
        user_id=333777,
        pr_number=953,
        date=timezone.now() - datetime.timedelta(days=5),
    )
    create_user_activity(
        account=account, user_id=333777, pr_number=953, date=timezone.now()
    )

    create_user_activity(
        account=account,
        user_id=90322322,
        pr_number=883,
        date=timezone.now() - datetime.timedelta(days=10),
    )
    create_user_activity(
        account=account, user_id=90322322, pr_number=883, date=timezone.now()
    )

    active_users = UserPullRequestActivity.get_active_users_in_last_30_days(account)
    assert len(active_users) == 2
    assert active_users[0].github_id == 90322322
    assert active_users[1].github_id == 333777
