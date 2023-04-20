import datetime
import json
from pathlib import Path

import pytest
from django.utils.timezone import make_aware

from web_api.models import Account, GitHubEvent, PullRequestActivity

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def pull_request_kodiak_updated() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_kodiak_updated.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.fixture
def pull_request_kodiak_merged() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_kodiak_merged.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.fixture
def pull_request_kodiak_approved() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request_review",
        # tood fixme installation wrong
        payload=json.load(
            (FIXTURES / "pull_request_review_kodiak_approved.json").open()
        ),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.fixture
def pull_request_total_opened() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_total_opened.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.fixture
def pull_request_total_merged() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_total_merged.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.fixture
def pull_request_total_closed() -> None:
    event = GitHubEvent.objects.create(
        event_name="pull_request",
        payload=json.load((FIXTURES / "pull_request_total_closed.json").open()),
    )
    event.created_at = make_aware(datetime.datetime(2020, 2, 13))  # noqa: DTZ001
    event.save()


@pytest.mark.django_db
def test_generate_activity_data(
    pull_request_kodiak_updated: object,
    pull_request_kodiak_merged: object,
    pull_request_kodiak_approved: object,
    pull_request_total_opened: object,
    pull_request_total_merged: object,
    pull_request_total_closed: object,
) -> None:
    assert PullRequestActivity.objects.count() == 0
    PullRequestActivity.generate_activity_data()

    assert PullRequestActivity.objects.count() == 1
    pull_request_activity = PullRequestActivity.objects.get()

    def check_response() -> None:
        assert pull_request_activity.date == datetime.date(2020, 2, 13)
        assert pull_request_activity.total_opened == 1
        assert (
            pull_request_activity.total_merged == 2
        ), "one user merge and one from kodiak"
        assert pull_request_activity.total_closed == 1
        assert pull_request_activity.kodiak_approved == 1
        assert pull_request_activity.kodiak_merged == 2
        assert pull_request_activity.kodiak_updated == 1
        # NOTE(chdsbd): I don't like how this field is called "account_id" when the
        # foreign key is on github_installation_id of an account.
        assert (
            pull_request_activity.github_installation_id == 848733
        ), "the ID of the installation from the json files"

    check_response()

    # running twice should update results and not hit database integrity errors
    # because we use INSERT ON CONFLICT.
    pull_request_activity.total_opened = 0
    pull_request_activity.total_merged = 0
    pull_request_activity.total_closed = 0
    pull_request_activity.kodiak_approved = 0
    pull_request_activity.kodiak_merged = 0
    pull_request_activity.kodiak_updated = 0
    pull_request_activity.save()

    PullRequestActivity.generate_activity_data()

    pull_request_activity.refresh_from_db()

    check_response()


@pytest.mark.django_db
def test_generate_activity_data_with_args(pull_request_total_closed: object) -> None:
    account = Account.objects.create(
        github_installation_id=848733,
        github_account_id=49153,
        github_account_login="chdsbd",
        github_account_type="User",
    )
    other_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login="recipeyak",
        github_account_type="User",
    )
    assert PullRequestActivity.objects.count() == 0

    # try with a date in the future of the pull request
    PullRequestActivity.generate_activity_data(min_date=datetime.date(2050, 5, 5))
    assert PullRequestActivity.objects.count() == 0, "our event should be excluded"

    # try with account for different organization
    PullRequestActivity.generate_activity_data(account=other_account)
    assert (
        PullRequestActivity.objects.count() == 0
    ), "we shouldn't have any events because this is a different account"

    PullRequestActivity.generate_activity_data(
        min_date=datetime.date(2000, 4, 13), account=account
    )
    assert (
        PullRequestActivity.objects.count() == 1
    ), "we should have an event because our pull_request_total_closed is after the min date and is on the same account"
    pull_request_activity = PullRequestActivity.objects.get()

    assert pull_request_activity.date == datetime.date(2020, 2, 13)
    assert pull_request_activity.total_opened == 0
    assert pull_request_activity.total_merged == 0
    assert pull_request_activity.total_closed == 1
    assert pull_request_activity.kodiak_approved == 0
    assert pull_request_activity.kodiak_merged == 0
    assert pull_request_activity.kodiak_updated == 0
