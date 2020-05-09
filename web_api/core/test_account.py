import datetime
from typing import Any

import pytest
import redis
from django.conf import settings
from django.utils.timezone import make_aware

from core.models import Account, AccountType, StripeCustomerInformation


@pytest.mark.django_db
def test_update_bot() -> None:
    """
    Should update subscription information in Redis
    """
    r = redis.Redis.from_url(settings.REDIS_URL)
    r.flushdb()
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
    )
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {}  # type: ignore
    assert r.exists("kodiak:refresh_pull_requests_for_installation") == 0
    account.update_bot()
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {  # type: ignore
        b"account_id": str(account.id).encode(),
        b"subscription_blocker": b"",
    }
    assert r.exists("kodiak:refresh_pull_requests_for_installation") == 1
    assert r.lrange("kodiak:refresh_pull_requests_for_installation", 0, -1) == [  # type: ignore
        ('{"installation_id": "%s"}' % account.github_installation_id).encode()
    ]


@pytest.mark.django_db
def test_get_subscription_blocker_ok() -> None:
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
    )
    assert account.get_subscription_blocker() is None


@pytest.mark.django_db
def test_get_subscription_blocker_subscription_expired() -> None:
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
    )
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
    assert account.get_subscription_blocker() == "subscription_expired"


@pytest.mark.django_db
def test_get_subscription_blocker_trial_expired() -> None:
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        trial_expiration=make_aware(datetime.datetime(1900, 2, 13)),
    )
    assert account.trial_expired() is True
    assert account.get_subscription_blocker() == "trial_expired"


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded(mocker: Any) -> None:
    get_active_users_in_last_30_days = mocker.patch(
        "core.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[1, 2, 3, 4, 5],
    )
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
    )
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
    assert get_active_users_in_last_30_days.call_count == 0
    assert account.get_active_user_count() == 5
    assert get_active_users_in_last_30_days.call_count == 1
    assert account.get_subscription_blocker() == "seats_exceeded"
    assert get_active_users_in_last_30_days.call_count == 2


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded_no_sub_or_trial(mocker: Any) -> None:
    """
    If an account has active users but no trial or subscription, that should
    trigger the paywall when the active user count has been exceeded.
    """
    get_active_users_in_last_30_days = mocker.patch(
        "core.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[1, 2, 3, 4, 5],
    )
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
    )
    assert account.github_account_type == AccountType.organization
    assert get_active_users_in_last_30_days.call_count == 0
    assert account.get_subscription_blocker() == "seats_exceeded"
    assert get_active_users_in_last_30_days.call_count == 1
    assert account.get_active_user_count() == 5

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
        "core.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[],
    )
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
    )
    assert account.get_subscription_blocker() is None
    assert account.get_active_user_count() == 0


@pytest.mark.django_db
def test_get_subscription_blocker_seats_exceeded_with_trial(mocker: Any) -> None:
    """
    If an account has active users but is on the trial we should allow them full
    access.
    """
    mocker.patch(
        "core.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[1, 2, 3, 4, 5],
    )
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
        trial_expiration=make_aware(datetime.datetime(2100, 2, 13)),
    )
    assert account.active_trial() is True
    assert account.get_active_user_count() == 5
    assert account.get_subscription_blocker() is None


@pytest.mark.django_db
def test_get_subscription_blocker_expired_trial_subscription_ok(mocker: Any) -> None:
    """
    If an account has a trial that is expired, but their subscription is valid,
    we should not raise the paywall.
    """
    mocker.patch(
        "core.models.UserPullRequestActivity.get_active_users_in_last_30_days",
        return_value=[1, 2, 3, 4, 5],
    )
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
        stripe_customer_id="cus_H2pvQ2kt7nk0JY",
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
