import datetime
from typing import Any, cast

import pytest
import responses
import stripe
from django.conf import settings
from django.utils import timezone

from core.models import (
    Account,
    AccountMembership,
    PullRequestActivity,
    StripeCustomerInformation,
    User,
    UserPullRequestActivity,
)
from core.testutils import TestClient as Client


@pytest.fixture
def user() -> User:
    return cast(
        User,
        User.objects.create(
            github_id=10137,
            github_login="ghost",
            github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
        ),
    )


@pytest.fixture
def other_user() -> User:
    return cast(
        User,
        User.objects.create(
            github_id=67647,
            github_login="bear",
            github_access_token="D2F92D26-BC64-427C-93CC-13E7110F3EB7",
        ),
    )


@pytest.fixture
def mocked_responses() -> Any:
    with responses.RequestsMock() as rsps:
        yield rsps


def test_environment() -> None:
    assert settings.KODIAK_API_GITHUB_CLIENT_ID == "Iv1.111FAKECLIENTID111"
    assert settings.KODIAK_API_GITHUB_CLIENT_SECRET == "888INVALIDSECRET8888"


@pytest.fixture
def authed_client(client: Client, user: User) -> Client:
    client.login(user)
    return client


@pytest.mark.django_db
def test_usage_billing(authed_client: Client, user: User, other_user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    # this user opened a PR on a private repository that Kodiak also acted on,
    # so we should count it.
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login=user.github_login,
        github_user_id=user.github_id,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=True,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=False,
    )

    # this user did not open a pull request, so we shouldn't count it.
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=864,
        github_user_login="jdoe",
        github_user_id=6039209,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 7),
        opened_pull_request=False,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=864,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=False,
    )

    # this event is on a public repository, so we shouldn't count it.
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=755,
        github_user_login="sgoodman",
        github_user_id=4323112,
        is_private_repository=False,
        activity_date=datetime.date(2020, 12, 7),
        opened_pull_request=True,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=755,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=False,
        activity_date=datetime.date(2020, 12, 5),
        opened_pull_request=False,
    )

    # this event should not be counted because the PR was not acted on by Kodiak.
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=8545,
        github_user_login="jpiccirillo",
        github_user_id=643453,
        is_private_repository=True,
        activity_date=datetime.date(2020, 12, 7),
        opened_pull_request=True,
    )

    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["activeUsers"] == [
        dict(
            id=user.github_id,
            name=user.github_login,
            profileImgUrl=user.profile_image(),
            interactions=1,
            lastActiveDate="2020-12-05",
        )
    ]


@pytest.mark.django_db
def test_usage_billing_trial_active(
    authed_client: Client, user: User, other_user: User,patch_start_trial: object
) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    user_account.start_trial(actor=user, billing_email="b.lowe@example.com")
    user_account.save()

    assert user_account.trial_expired() is False
    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["trial"] is not None
    assert isinstance(res.json()["trial"]["startDate"], str)
    assert isinstance(res.json()["trial"]["endDate"], str)
    assert res.json()["trial"]["expired"] is False
    assert res.json()["trial"]["startedBy"] == dict(
        id=str(user.id), name=user.github_login, profileImgUrl=user.profile_image()
    )


@pytest.mark.django_db
def test_usage_billing_trial_expired(
    authed_client: Client, user: User, other_user: User,patch_start_trial: object
) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    user_account.start_trial(actor=user, billing_email="b.lowe@example.com")
    user_account.trial_start = timezone.make_aware(datetime.datetime(2000, 4, 15))
    user_account.trial_expiration = timezone.make_aware(datetime.datetime(2000, 5, 4))
    user_account.save()
    assert datetime.datetime.now() > datetime.datetime(
        2000, 5, 4
    ), "we expect the current time to be more recent"

    assert user_account.trial_expired() is True
    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["trial"] is not None
    assert res.json()["trial"] == dict(
        startDate="2000-04-15T00:00:00Z",
        endDate="2000-05-04T00:00:00Z",
        expired=True,
        startedBy=dict(
            id=str(user.id), name=user.github_login, profileImgUrl=user.profile_image()
        ),
    )


@pytest.mark.django_db
def test_usage_billing_authentication(authed_client: Client, other_user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 404


@pytest.mark.django_db
def test_usage_billing_subscription_started(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = 1650581784
    period_end = 1655765784 + 30 * ONE_DAY_SEC  # start plus one month.
    mocker.patch("core.models.time.time", return_value=period_start + 5 * ONE_DAY_SEC)
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    StripeCustomerInformation.objects.create(
        customer_id=account.stripe_customer_id,
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
        subscription_current_period_start=period_start,
        subscription_current_period_end=period_end,
    )
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscription"] is not None
    assert res.json()["subscription"]["nextBillingDate"] == "2022-07-20T22:56:24"
    assert res.json()["subscription"]["expired"] is False
    assert res.json()["subscription"]["seats"] == 3
    assert res.json()["subscription"]["cost"]["totalCents"] == 3 * 499
    assert res.json()["subscription"]["cost"]["perSeatCents"] == 499
    assert res.json()["subscription"]["billingEmail"] == "accounting@acme-corp.com"


@pytest.mark.django_db
def test_update_subscription(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = 1650581784
    period_end = 1655765784 + 30 * ONE_DAY_SEC  # start plus one month.
    # fake_subscription = stripe.Subscription(id='sub_Gu1xedsfo1', items=dict(data=[stripe.SubscriptionItem(id='si_Gx234091sd2')]))
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            current_period_end=period_start,
            current_period_start=period_end,
            items=dict(data=[dict(object="subscription_item", id="si_Gx234091sd2")]),
            plan=dict(id="plan_G2df31A4G5JzQ", object="plan", amount=499,),
            quantity=4,
        ),
        "fake-key",
    )

    stripe_subscription_retrieve = mocker.patch(
        "core.models.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    stripe_subscription_modify = mocker.patch(
        "core.models.stripe.Subscription.modify", return_value=fake_subscription
    )
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    StripeCustomerInformation.objects.create(
        customer_id=account.stripe_customer_id,
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
        subscription_current_period_start=period_start,
        subscription_current_period_end=period_end,
    )
    assert stripe_subscription_retrieve.call_count == 0
    assert stripe_subscription_modify.call_count == 0
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(prorationTimestamp=period_start + 4 * ONE_DAY_SEC, seats=24),
    )
    assert res.status_code == 204
    assert stripe_subscription_retrieve.call_count == 1
    assert stripe_subscription_modify.call_count == 1


@pytest.mark.django_db
def test_update_subscription_missing_customer(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            items=dict(data=[dict(object="subscription_item", id="si_Gx234091sd2")]),
        ),
        "fake-key",
    )

    stripe_subscription_retrieve = mocker.patch(
        "core.models.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    stripe_subscription_modify = mocker.patch(
        "core.models.stripe.Subscription.modify", return_value=fake_subscription
    )
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    assert StripeCustomerInformation.objects.count() == 0
    assert stripe_subscription_retrieve.call_count == 0
    assert stripe_subscription_modify.call_count == 0
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(prorationTimestamp=1650581784, seats=24),
    )
    assert res.status_code == 422
    assert res.json()["message"] == "Subscription does not exist to modify."
    assert stripe_subscription_retrieve.call_count == 0
    assert stripe_subscription_modify.call_count == 0


@pytest.mark.django_db
def test_cancel_subscription(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = 1650581784
    period_end = 1655765784 + 30 * ONE_DAY_SEC  # start plus one month.
    patched = mocker.patch("core.models.stripe.Subscription.delete")
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    StripeCustomerInformation.objects.create(
        customer_id=account.stripe_customer_id,
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
        subscription_current_period_start=period_start,
        subscription_current_period_end=period_end,
    )
    assert patched.call_count == 0
    assert StripeCustomerInformation.objects.count() == 1
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 204
    assert patched.call_count == 1
    assert StripeCustomerInformation.objects.count() == 0


@pytest.mark.django_db
def test_activity(authed_client: Client, user: User,) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    pull_request_activity = PullRequestActivity.objects.create(
        date=datetime.date(2020, 2, 3),
        total_opened=15,
        total_merged=13,
        total_closed=2,
        kodiak_approved=3,
        kodiak_merged=12,
        kodiak_updated=2,
        github_installation_id=user_account.github_installation_id,
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 200
    assert res.json()["kodiakActivity"]["labels"] == ["2020-02-03"]
    assert res.json()["kodiakActivity"]["datasets"] == {
        "approved": [pull_request_activity.kodiak_approved],
        "merged": [pull_request_activity.kodiak_merged],
        "updated": [pull_request_activity.kodiak_updated],
    }
    assert res.json()["pullRequestActivity"]["labels"] == ["2020-02-03"]
    assert res.json()["pullRequestActivity"]["datasets"] == {
        "opened": [pull_request_activity.total_opened],
        "merged": [pull_request_activity.total_merged],
        "closed": [pull_request_activity.total_closed],
    }


@pytest.mark.django_db
def test_start_checkout(authed_client: Client, user: User, mocker: Any) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    class FakeCheckoutSession:
        id = "cs_tgn3bJHRrXhqgdVSc4tsY"

    mocker.patch(
        "core.views.stripe.checkout.Session.create", return_value=FakeCheckoutSession
    )
    res = authed_client.post(
        f"/v1/t/{user_account.id}/start_checkout", dict(seatCount=3)
    )
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id


@pytest.mark.django_db
def test_modify_payment_details(authed_client: Client, user: User, mocker: Any) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    class FakeCheckoutSession:
        id = "cs_tgn3bJHRrXhqgdVSc4tsY"

    mocker.patch(
        "core.views.stripe.checkout.Session.create", return_value=FakeCheckoutSession
    )
    res = authed_client.post(f"/v1/t/{user_account.id}/modify_payment_details")
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id


@pytest.mark.django_db
def test_activity_authentication(authed_client: Client, other_user: User,) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 404


@pytest.mark.django_db
def test_sync_accounts_success(
    authed_client: Client, successful_sync_accounts_response: object
) -> None:
    assert Account.objects.count() == 0
    res = authed_client.post("/v1/sync_accounts")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert Account.objects.count() == 1


@pytest.mark.django_db
def test_sync_accounts_failure(
    authed_client: Client, failing_sync_accounts_response: object
) -> None:
    assert Account.objects.count() == 0
    res = authed_client.post("/v1/sync_accounts")
    assert res.status_code == 200
    assert res.json()["ok"] is False
    assert Account.objects.count() == 0


@pytest.mark.django_db
def test_current_account(authed_client: Client, user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = Account.objects.create(
        github_installation_id=83676,
        github_account_id=779874,
        github_account_login="recipeyak",
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=org_account, user=user, role="member")

    res = authed_client.get(f"/v1/t/{org_account.id}/current_account")
    assert res.status_code == 200
    assert res.json()["user"]["id"] == str(user.id)
    assert res.json()["user"]["name"] == user.github_login
    assert (
        res.json()["user"]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user.github_id}"
    )
    assert res.json()["org"]["id"] == str(org_account.id)
    assert res.json()["org"]["name"] == org_account.github_account_login
    assert (
        res.json()["org"]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{org_account.github_account_id}"
    )

    assert len(res.json()["accounts"]) == 2
    accounts = sorted(res.json()["accounts"], key=lambda x: x["name"])
    assert accounts[0]["id"] == str(user_account.id)
    assert accounts[0]["name"] == user_account.github_account_login
    assert (
        accounts[0]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user_account.github_account_id}"
    )


@pytest.mark.django_db
def test_current_account_authentication(
    authed_client: Client, other_user: User,
) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=other_user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/current_account")
    assert res.status_code == 404


@pytest.mark.django_db
def test_accounts(authed_client: Client, user: User) -> None:
    user_account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = Account.objects.create(
        github_installation_id=83676,
        github_account_id=779874,
        github_account_login="recipeyak",
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=org_account, user=user, role="member")

    res = authed_client.get("/v1/accounts")
    assert res.status_code == 200
    assert len(res.json()) == 2
    accounts = sorted(res.json(), key=lambda x: x["name"])
    assert accounts[0]["id"] == str(user_account.id)
    assert accounts[0]["name"] == user_account.github_account_login
    assert (
        accounts[0]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user_account.github_account_id}"
    )


@pytest.fixture
def patch_start_trial(mocker: Any) -> None:
    fake_customer = stripe.Customer.construct_from(
        dict(object="customer", id="cust_Gx2a3gd5x6",), "fake-key",
    )
    mocker.patch("core.models.stripe.Customer.create", return_value=fake_customer)


@pytest.mark.django_db
def test_start_trial(
    authed_client: Client, user: User, patch_start_trial: object
) -> None:
    """
    When a user starts a trial we should update their account.
    """
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    assert account.trial_start is None
    assert account.trial_expiration is None
    assert account.trial_started_by is None
    assert (
        account.trial_expired() is False
    ), "when a trial is inactive, it shouldn't have expired."
    res = authed_client.post(
        f"/v1/t/{account.id}/start_trial", dict(billingEmail="b.lowe@example.com")
    )
    assert res.status_code == 204
    account.refresh_from_db()
    assert account.trial_start is not None
    assert (
        (account.trial_start - account.trial_expiration).total_seconds()
        - datetime.timedelta(days=14).total_seconds()
        < 60 * 60
    ), "times should be within an hour of each other. This should hopefully avoid flakiness around dates."
    assert account.trial_started_by == user
    assert account.trial_expired() is False


def equal_dates(a: datetime.datetime, b: datetime.datetime) -> bool:
    """
    Dates are equal if they are within 5 minutes of each other. This should
    hopefully reduce flakiness is tests.
    """
    return abs(int(a.timestamp()) - int(b.timestamp())) < 60 * 5


@pytest.mark.django_db
def test_start_trial_existing_trial(
    authed_client: Client, user: User, patch_start_trial: object
) -> None:
    """
    Starting a trial when there is already an existing trial shouldn't alter
    current trial.
    """
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    account.start_trial(actor=user, billing_email="b.lowe@example.com", length_days=2)
    original_trial_start = account.trial_start
    original_trial_expiration = account.trial_expiration
    original_trial_started_by = account.trial_started_by

    res = authed_client.post(
        f"/v1/t/{account.id}/start_trial", dict(billingEmail="d.abernathy@example.com")
    )
    assert res.status_code == 204
    account.refresh_from_db()
    assert equal_dates(account.trial_start, original_trial_start)
    assert equal_dates(account.trial_expiration, original_trial_expiration)
    assert account.trial_started_by == original_trial_started_by


@pytest.mark.django_db
def test_logout(client: Client, user: User) -> None:
    """
    Ensure we delete the cookie on logout.
    The user should no longer be able to access authed routes.
    """
    client.login(user)
    res = client.get("/v1/ping")
    assert res.status_code == 200
    res = client.get("/v1/logout")
    assert res.status_code == 201
    res = client.get("/v1/ping")
    assert res.status_code == 401


@pytest.mark.django_db
def test_oauth_login(client: Client, state_token: str) -> None:
    res = client.get("/v1/oauth_login", dict(state=state_token))
    assert res.status_code == 302
    assert (
        res["Location"]
        == f"https://github.com/login/oauth/authorize?client_id=Iv1.111FAKECLIENTID111&redirect_uri=https://app.kodiakhq.com/oauth&state={state_token}"
    )


@pytest.fixture
def successful_sync_accounts_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "total_count": 1,
            "installations": [
                {
                    "id": 1066615,
                    "account": {
                        "login": "chdsbd",
                        "id": 1929960,
                        "node_id": "MDQ6VXNlcjE5Mjk5NjA=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/1929960?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/chdsbd",
                        "html_url": "https://github.com/chdsbd",
                        "followers_url": "https://api.github.com/users/chdsbd/followers",
                        "following_url": "https://api.github.com/users/chdsbd/following{/other_user}",
                        "gists_url": "https://api.github.com/users/chdsbd/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/chdsbd/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/chdsbd/subscriptions",
                        "organizations_url": "https://api.github.com/users/chdsbd/orgs",
                        "repos_url": "https://api.github.com/users/chdsbd/repos",
                        "events_url": "https://api.github.com/users/chdsbd/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/chdsbd/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/1066615/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/1066615",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 1929960,
                    "target_type": "User",
                    "permissions": {
                        "administration": "read",
                        "checks": "write",
                        "contents": "write",
                        "issues": "read",
                        "metadata": "read",
                        "pull_requests": "write",
                        "statuses": "read",
                    },
                    "events": [
                        "check_run",
                        "issue_comment",
                        "pull_request",
                        "pull_request_review",
                        "pull_request_review_comment",
                        "push",
                        "status",
                    ],
                    "created_at": "2019-05-26T23:47:57.000-04:00",
                    "updated_at": "2020-02-09T18:39:43.000-05:00",
                    "single_file_name": None,
                }
            ],
        },
    )


@pytest.fixture
def successful_responses(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.POST,
        "https://github.com/login/oauth/access_token",
        body="access_token=D6B5A3B57D32498DB00845A99137D3E2&token_type=bearer",
        status=200,
        content_type="application/x-www-form-urlencoded",
    )

    # https://developer.github.com/v3/users/#response-with-public-and-private-profile-information
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user",
        json={
            "login": "ghost",
            "id": 10137,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/ghost_happy.gif",
            "gravatar_id": "",
            "url": "https://api.github.com/users/ghost",
            "html_url": "https://github.com/ghost",
            "followers_url": "https://api.github.com/users/ghost/followers",
            "following_url": "https://api.github.com/users/ghost/following{/other_user}",
            "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
            "organizations_url": "https://api.github.com/users/ghost/orgs",
            "repos_url": "https://api.github.com/users/ghost/repos",
            "events_url": "https://api.github.com/users/ghost/events{/privacy}",
            "received_events_url": "https://api.github.com/users/ghost/received_events",
            "type": "User",
            "site_admin": False,
            "name": "monalisa ghost",
            "company": "GitHub",
            "blog": "https://github.com/blog",
            "location": "San Francisco",
            "email": "ghost@github.com",
            "hireable": False,
            "bio": "There once was...",
            "public_repos": 2,
            "public_gists": 1,
            "followers": 20,
            "following": 0,
            "created_at": "2008-01-14T04:33:35Z",
            "updated_at": "2008-01-14T04:33:35Z",
            "private_gists": 81,
            "total_private_repos": 100,
            "owned_private_repos": 100,
            "disk_usage": 10000,
            "collaborators": 8,
            "two_factor_authentication": True,
            "plan": {
                "name": "Medium",
                "space": 400,
                "private_repos": 20,
                "collaborators": 0,
            },
        },
        status=200,
    )


@pytest.mark.django_db
def test_oauth_complete_success_new_account(
    client: Client,
    state_token: str,
    successful_responses: object,
    successful_sync_accounts_response: object,
) -> None:
    assert Account.objects.count() == 0
    assert User.objects.count() == 0
    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    assert Account.objects.count() == 1
    user = User.objects.get()
    assert user.github_id == 10137
    assert user.github_login == "ghost"
    assert user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"


@pytest.mark.django_db
def test_oauth_complete_success_existing_account(
    client: Client,
    user: User,
    successful_responses: object,
    successful_sync_accounts_response: object,
    state_token: str,
) -> None:
    assert User.objects.count() == 1

    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is True
    assert User.objects.count() == 1
    new_user = User.objects.get()
    assert new_user.github_id == user.github_id
    assert new_user.github_login == user.github_login
    assert new_user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"


@pytest.fixture
def failing_sync_accounts_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "message": "Bad credentials",
            "documentation_url": "https://developer.github.com/v3",
        },
        status=401,
    )


@pytest.mark.django_db
def test_oauth_complete_sync_installation_failure(
    client: Client,
    successful_responses: object,
    failing_sync_accounts_response: object,
    state_token: str,
) -> None:

    assert User.objects.count() == 0
    assert Account.objects.count() == 0
    res = client.post(
        "/v1/oauth_complete",
        dict(
            serverState=state_token,
            clientState=state_token,
            code="D86BE2B3F3C74ACB91D3DF7B649F40BB",
        ),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is False
    assert login_result["error"] == "AccountSyncFailure"
    assert (
        login_result["error_description"] == "Failed to sync GitHub accounts for user."
    )
    assert User.objects.count() == 1
    user = User.objects.get()
    assert user.github_id == 10137
    assert user.github_login == "ghost"
    assert user.github_access_token == "D6B5A3B57D32498DB00845A99137D3E2"
    assert Account.objects.count() == 0


@pytest.mark.skip
def test_oauth_complete_cookie_session_mismatch(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fail_to_fetch_access_token(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fetch_access_token_qs_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fetch_access_token_res_error(client: Client) -> None:
    assert False


@pytest.mark.skip
def test_oauth_complete_fail_fetch_github_account_info(client: Client) -> None:
    assert False


@pytest.fixture
def state_token(client: Client) -> str:
    return "71DDCF95-84FC-4A5F-BCBF-BEB5FCCBDEA8"


@pytest.mark.django_db
def test_oauth_complete_missing_code(client: Client, state_token: str) -> None:
    res = client.post(
        "/v1/oauth_complete", dict(serverState=state_token, clientState=state_token,),
    )
    assert res.status_code == 200

    login_result = res.json()
    assert login_result["ok"] is False
    assert login_result["error"] == "OAuthMissingCode"
    assert login_result["error_description"] == "Payload should have a code parameter."
