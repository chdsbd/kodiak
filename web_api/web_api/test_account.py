import datetime
from typing import Any, Optional, cast

import pytest
import redis
from django.conf import settings
from django.utils.timezone import make_aware

from web_api.models import (
    Account,
    AccountMembership,
    AccountType,
    ActiveUser,
    StripeCustomerInformation,
    User,
    UserPullRequestActivity,
)


@pytest.mark.django_db
def test_update_bot() -> None:
    """
    Should update subscription information in Redis
    """
    r = redis.Redis.from_url(settings.REDIS_URL)
    r.flushdb()
    account = create_account(trial_expiration=None)
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {}  # type: ignore
    assert r.exists("kodiak:refresh_pull_requests_for_installation") == 0
    account.update_bot()
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {  # type: ignore
        b"account_id": str(account.id).encode(),
        b"data": b"",
        b"subscription_blocker": b"",
    }
    assert r.exists("kodiak:refresh_pull_requests_for_installation") == 1
    assert r.lrange("kodiak:refresh_pull_requests_for_installation", 0, -1) == [  # type: ignore
        ('{"installation_id": "%s"}' % account.github_installation_id).encode()
    ]


@pytest.mark.django_db
def test_get_subscription_blocker_ok() -> None:
    account = create_account(trial_expiration=None)
    assert account.get_subscription_blocker() is None


@pytest.mark.django_db
def test_get_subscription_blocker_subscription_expired() -> None:
    account = create_account(trial_expiration=None)
    stripe_customer_information = StripeCustomerInformation.objects.create(
        customer_id="cus_H2pvQ2kt7nk0JY",
        subscription_id="sub_Gu1xedsfo1",
        plan_id="plan_G2df31A4G5JzQ",
        payment_method_id="pm_22dldxf3",
        customer_email="accounting@acme-corp.com",
        customer_balance=0,
        customer_created=1585781308,
        payment_method_card_brand="mastercard",
        payment_method_card_exp_month="03",
        payment_method_card_exp_year="32",
        payment_method_card_last4="4242",
        plan_amount=499,
        subscription_quantity=3,
        subscription_start_date=1585781784,
        #
        subscription_current_period_start=0,
        subscription_current_period_end=100,
    )

    assert stripe_customer_information.expired is True
    blocker = account.get_subscription_blocker()
    assert blocker is not None
    assert blocker.kind == "subscription_expired"


@pytest.mark.django_db
def test_get_subscription_blocker_trial_expired() -> None:
    account = create_account(
        trial_expiration=make_aware(datetime.datetime(1900, 2, 13)),
    )
    assert account.trial_expired() is True
    blocker = account.get_subscription_blocker()
    assert blocker is not None
    assert blocker.kind == "trial_expired"


@pytest.fixture
def patched_get_active_users_in_last_30_days(mocker: Any) -> Any:
    return mocker.patch(
        "web_api.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[
            ActiveUser(
                github_login="alpha",
                github_id=1,
                days_active=1,
                first_active_at=datetime.date(2020, 4, 4),
                last_active_at=datetime.date(2020, 4, 4),
            ),
            ActiveUser(
                github_login="bravo",
                github_id=1,
                days_active=1,
                first_active_at=datetime.date(2020, 4, 4),
                last_active_at=datetime.date(2020, 4, 4),
            ),
            ActiveUser(
                github_login="charlie",
                github_id=2,
                days_active=2,
                first_active_at=datetime.date(2020, 4, 4),
                last_active_at=datetime.date(2020, 4, 4),
            ),
            ActiveUser(
                github_login="delta",
                github_id=3,
                days_active=3,
                first_active_at=datetime.date(2020, 4, 4),
                last_active_at=datetime.date(2020, 4, 4),
            ),
            ActiveUser(
                github_login="echo",
                github_id=4,
                days_active=4,
                first_active_at=datetime.date(2020, 4, 4),
                last_active_at=datetime.date(2020, 4, 4),
            ),
        ],
    )


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded(
    patched_get_active_users_in_last_30_days: Any,
) -> None:
    account = create_account(trial_expiration=None)
    stripe_customer_information = StripeCustomerInformation.objects.create(
        customer_id="cus_H2pvQ2kt7nk0JY",
        subscription_id="sub_Gu1xedsfo1",
        plan_id="plan_G2df31A4G5JzQ",
        payment_method_id="pm_22dldxf3",
        customer_email="accounting@acme-corp.com",
        customer_balance=0,
        customer_created=1585781308,
        payment_method_card_brand="mastercard",
        payment_method_card_exp_month="03",
        payment_method_card_exp_year="32",
        payment_method_card_last4="4242",
        plan_amount=499,
        subscription_quantity=3,
        subscription_start_date=1585781784,
        #
        subscription_current_period_start=0,
        subscription_current_period_end=1987081359,
    )
    assert stripe_customer_information.expired is False
    assert patched_get_active_users_in_last_30_days.call_count == 0
    assert (
        len(UserPullRequestActivity.get_active_users_in_last_30_days(account=account))
        == 5
    )
    assert patched_get_active_users_in_last_30_days.call_count == 1
    blocker = account.get_subscription_blocker()
    assert blocker is not None
    assert blocker.kind == "seats_exceeded"
    assert patched_get_active_users_in_last_30_days.call_count == 2


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded_no_sub_or_trial(
    patched_get_active_users_in_last_30_days: Any,
) -> None:
    """
    If an account has active users but no trial or subscription, that should
    trigger the paywall when the active user count has been exceeded.
    """
    account = create_account(trial_expiration=None)
    assert account.github_account_type == AccountType.organization
    assert patched_get_active_users_in_last_30_days.call_count == 0
    blocker = account.get_subscription_blocker()
    assert blocker is not None
    assert blocker.kind == "seats_exceeded"
    assert patched_get_active_users_in_last_30_days.call_count == 1
    assert (
        len(UserPullRequestActivity.get_active_users_in_last_30_days(account=account))
        == 5
    )

    account.github_account_type = AccountType.user
    account.save()
    assert account.get_subscription_blocker() is None


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded_no_sub_or_trial_no_activity(
    mocker: Any,
) -> None:
    """
    If an account has no trial or subscription, but also no active users, we
    should not raise the paywall.
    """
    mocker.patch(
        "web_api.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[],
    )
    account = create_account(trial_expiration=None)
    assert account.get_subscription_blocker() is None
    assert (
        len(UserPullRequestActivity.get_active_users_in_last_30_days(account=account))
        == 0
    )


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded_with_trial(
    patched_get_active_users_in_last_30_days: Any,
) -> None:
    """
    If an account has active users but is on the trial we should allow them full
    access.
    """
    account = create_account(
        trial_expiration=make_aware(datetime.datetime(2100, 2, 13)),
    )
    assert account.active_trial() is True
    assert (
        len(UserPullRequestActivity.get_active_users_in_last_30_days(account=account))
        == 5
    )
    assert account.get_subscription_blocker() is None


def create_account(
    trial_expiration: Optional[datetime.datetime] = make_aware(
        datetime.datetime(1900, 2, 13)
    )
) -> Account:
    return cast(
        Account,
        Account.objects.create(
            github_installation_id=1066615,
            github_account_login="acme-corp",
            github_account_id=523412234,
            github_account_type="Organization",
            stripe_customer_id="cus_H2pvQ2kt7nk0JY",
            trial_expiration=trial_expiration,
        ),
    )


@pytest.mark.django_db
def test_get_subscription_blocker_expired_trial_subscription_ok(
    patched_get_active_users_in_last_30_days: Any,
) -> None:
    """
    If an account has a trial that is expired, but their subscription is valid,
    we should not raise the paywall.
    """
    account = create_account(
        trial_expiration=make_aware(datetime.datetime(1900, 2, 13)),
    )
    StripeCustomerInformation.objects.create(
        customer_id="cus_H2pvQ2kt7nk0JY",
        subscription_id="sub_Gu1xedsfo1",
        plan_id="plan_G2df31A4G5JzQ",
        payment_method_id="pm_22dldxf3",
        customer_email="accounting@acme-corp.com",
        customer_balance=0,
        customer_created=1585781308,
        payment_method_card_brand="mastercard",
        payment_method_card_exp_month="03",
        payment_method_card_exp_year="32",
        payment_method_card_last4="4242",
        plan_amount=499,
        subscription_quantity=10,
        subscription_start_date=1585781784,
        #
        subscription_current_period_start=0,
        subscription_current_period_end=1987081359,
    )
    assert account.trial_expired() is True
    assert account.get_subscription_blocker() is None


def create_user() -> User:
    return cast(User, User.objects.create(github_id=2341234, github_login="b-lowe"))


@pytest.mark.django_db
def test_can_edit_subscription() -> None:
    account = create_account()
    user = create_user()

    account.limit_billing_access_to_owners = False
    assert user.can_edit_subscription(account) is True

    account.limit_billing_access_to_owners = True
    assert user.can_edit_subscription(account) is False

    account.limit_billing_access_to_owners = True
    membership = AccountMembership.objects.create(
        account=account, user=user, role="member"
    )
    assert user.can_edit_subscription(account) is False

    account.limit_billing_access_to_owners = True
    membership.role = "admin"
    membership.save()
    assert user.can_edit_subscription(account) is True


def test_account_can_subscribe() -> None:
    """
    Organization accounts that are missing exemptions can subscribe.

    GitHub user accounts and accounts marked as exempt cannot subscribe.
    """
    assert (
        Account(github_account_type=AccountType.user).can_subscribe() is False
    ), "user accounts cannot subscribe"
    assert (
        Account(github_account_type=AccountType.organization).can_subscribe() is True
    ), "organization accounts can subscribe"
    assert (
        Account(
            github_account_type=AccountType.organization, subscription_exempt=True
        ).can_subscribe()
        is False
    ), "organization accounts with an exemption cannot subscribe"
