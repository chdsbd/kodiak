import datetime
import json
import time
from typing import Any, Union, cast

import pytest
import responses
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from core.models import (
    Account,
    AccountMembership,
    AccountType,
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
    assert (
        res.json()["accountCanSubscribe"] is False
    ), "user accounts should not see subscription options"
    assert res.json()["activeUsers"] == [
        dict(
            id=user.github_id,
            name=user.github_login,
            profileImgUrl=user.profile_image(),
            interactions=1,
            firstActiveDate="2020-12-01",
            lastActiveDate="2020-12-05",
            hasSeatLicense=False,
        )
    ]

    user_account.github_account_type = AccountType.organization
    user_account.save()
    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert (
        res.json()["accountCanSubscribe"] is True
    ), "organizations should see subscription options"


@pytest.mark.django_db
def test_usage_billing_trial_active(
    authed_client: Client, user: User, other_user: User, patch_start_trial: object
) -> None:
    """
    When the Account has an active trial, we return trial information in the API response.
    """
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
    authed_client: Client, user: User, other_user: User, patch_start_trial: object
) -> None:
    """
    When the Account has an expired trial, we return trial information in the
    API response and indicate that the trial is expired.
    """
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
    """
    When the Account has an active subscription we should return the
    subscription information in the API response.
    """
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = int(time.time())
    period_end = period_start + 30 * ONE_DAY_SEC  # start plus one month.
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
    assert (
        res.json()["subscription"]["nextBillingDate"]
        == datetime.datetime.fromtimestamp(period_end).isoformat()
    )
    assert res.json()["subscription"]["expired"] is False
    assert res.json()["subscription"]["seats"] == 3
    assert res.json()["subscription"]["cost"]["totalCents"] == 3 * 499
    assert res.json()["subscription"]["cost"]["perSeatCents"] == 499
    assert res.json()["subscription"]["billingEmail"] == "accounting@acme-corp.com"
    assert res.json()["subscription"]["cardInfo"] == "Mastercard (4242)"


@pytest.mark.django_db
def test_update_subscription(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    Verify that updating an Account's subscription updates Stripe.
    """
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = int(time.time())
    period_end = period_start + 30 * ONE_DAY_SEC  # start plus one month.
    update_bot = mocker.patch("core.models.Account.update_bot")
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            current_period_end=period_start,
            current_period_start=period_end,
            items=dict(data=[dict(object="subscription_item", id="si_Gx234091sd2")]),
            plan=dict(id="plan_G2df31A4G5JzQ", object="plan", amount=499,),
            quantity=4,
            default_payment_method="pm_22dldxf3",
        ),
        "fake-key",
    )

    stripe_subscription_retrieve = mocker.patch(
        "core.models.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    stripe_subscription_modify = mocker.patch(
        "core.models.stripe.Subscription.modify", return_value=fake_subscription
    )
    fake_invoice = stripe.Invoice.construct_from(
        dict(object="invoice", id="in_00000000000000"), "fake-key",
    )
    stripe_invoice_create = mocker.patch(
        "core.models.stripe.Invoice.create", return_value=fake_invoice
    )
    stripe_invoice_pay = mocker.patch("core.models.stripe.Invoice.pay")
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="admin")
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
    assert update_bot.call_count == 0
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(prorationTimestamp=period_start + 4 * ONE_DAY_SEC, seats=24),
    )
    assert res.status_code == 204
    assert stripe_subscription_retrieve.call_count == 1
    assert update_bot.call_count == 1
    assert stripe_subscription_modify.call_count == 1
    assert stripe_invoice_create.call_count == 1
    assert stripe_invoice_pay.call_count == 1


@pytest.mark.django_db
def test_update_subscription_missing_customer(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    We should get an error when we try to update a subscription for an Account
    that doesn't have an associated subscription.
    """
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
    AccountMembership.objects.create(account=account, user=user, role="admin")
    assert (
        StripeCustomerInformation.objects.count() == 0
    ), "we shouldn't have an associated subscription for this test."
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
def test_update_subscription_not_admin(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    Only admins should be able to modify subscriptions.
    """
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(prorationTimestamp=1650581784, seats=24),
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_cancel_subscription(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    Canceling a subscription should immediately cancel the subscription in Stripe.
    """
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = int(time.time())
    period_end = period_start + 30 * ONE_DAY_SEC  # start plus one month.
    patched = mocker.patch("core.models.stripe.Subscription.delete")
    update_bot = mocker.patch("core.models.Account.update_bot")
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
        stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="admin")
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
    assert update_bot.call_count == 0
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 204
    assert update_bot.call_count == 1
    assert patched.call_count == 1
    assert StripeCustomerInformation.objects.count() == 0


@pytest.mark.django_db
def test_cancel_subscription_not_admin(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    Only admins should be able to cancel a subscription.
    """
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
        subscription_current_period_start=1650581784,
        subscription_current_period_end=1658357784,
    )
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 403


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
def test_start_checkout(authed_client: Client, user: User, mocker: Any) -> None:
    """
    Start a Stripe checkout session and return the required credentials to the frontend.
    """
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
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY


@pytest.mark.django_db
def test_modify_payment_details(authed_client: Client, user: User, mocker: Any) -> None:
    """
    Start a new checkout session in "setup" mode to update the payment information.
    """
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
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY


@pytest.mark.django_db
def test_accounts_endpoint_ordering(authed_client: Client, user: User) -> None:
    """
    Ensure we order the accounts in the response by name.

    We could also sort them on the frontend.
    """
    industries = Account.objects.create(
        github_installation_id=125,
        github_account_login="industries",
        github_account_id=2234,
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=industries, user=user, role="member")

    acme = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=acme, user=user, role="member")

    market = Account.objects.create(
        github_installation_id=540,
        github_account_login="market",
        github_account_id=1020,
        github_account_type="Organization",
    )
    AccountMembership.objects.create(account=market, user=user, role="member")

    res = authed_client.get("/v1/accounts")
    assert res.json() == [
        {
            "id": str(acme.id),
            "name": "acme-corp",
            "profileImgUrl": "https://avatars.githubusercontent.com/u/523412234",
        },
        {
            "id": str(industries.id),
            "name": "industries",
            "profileImgUrl": "https://avatars.githubusercontent.com/u/2234",
        },
        {
            "id": str(market.id),
            "name": "market",
            "profileImgUrl": "https://avatars.githubusercontent.com/u/1020",
        },
    ]


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
    mocker.patch("core.models.stripe.Customer.modify", return_value=fake_customer)


@pytest.mark.django_db
def test_start_trial(
    authed_client: Client, user: User, patch_start_trial: object, mocker: Any
) -> None:
    """
    When a user starts a trial we should update their account.
    """
    update_bot = mocker.patch("core.models.Account.update_bot")
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
    assert update_bot.call_count == 1
    account.refresh_from_db()
    assert account.trial_start is not None
    assert (
        (account.trial_start - account.trial_expiration).total_seconds()
        - datetime.timedelta(days=30).total_seconds()
        < 60 * 60
    ), "times should be within an hour of each other. This should hopefully avoid flakiness around dates."
    assert account.trial_started_by == user
    assert account.trial_expired() is False
    assert account.trial_email == "b.lowe@example.com"


def similar_dates(a: datetime.datetime, b: datetime.datetime) -> bool:
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
    assert similar_dates(account.trial_start, original_trial_start)
    assert similar_dates(account.trial_expiration, original_trial_expiration)
    assert account.trial_started_by == original_trial_started_by


def generate_header(payload: str) -> str:
    """
    https://github.com/stripe/stripe-python/blob/a16bdc5123bcc25e20b309419f547a150e83e44d/tests/test_webhook.py#L19
    """
    secret = settings.STRIPE_WEBHOOK_SECRET
    timestamp = int(time.time())
    payload_to_sign = "%d.%s" % (timestamp, payload)
    scheme = stripe.WebhookSignature.EXPECTED_SCHEME
    signature = stripe.WebhookSignature._compute_signature(payload_to_sign, secret)
    return "t=%d,%s=%s" % (timestamp, scheme, signature)


def test_generate_header() -> None:
    """
    https://github.com/stripe/stripe-python/blob/a16bdc5123bcc25e20b309419f547a150e83e44d/tests/test_webhook.py#L19
    """
    payload_v2 = json.dumps({"blah": 123})
    header = generate_header(payload_v2)
    event = stripe.Webhook.construct_event(
        payload_v2, header, settings.STRIPE_WEBHOOK_SECRET
    )
    assert isinstance(event, stripe.Event)


def post_webhook(event: Union[dict, str]) -> HttpResponse:
    """
    Send a signed payload to our stripe webhook endpoint
    """
    if isinstance(event, str):
        payload = event
    else:
        payload = json.dumps(event)
    sig_header = generate_header(payload)
    return Client().post(
        "/v1/stripe_webhook",
        payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sig_header,
    )


@pytest.mark.django_db
def test_stripe_webhook_handler_checkout_session_complete_setup(mocker: Any) -> None:
    """
    Verify our webhook handler updates our subscription on this event.
    """
    update_bot = mocker.patch("core.models.Account.update_bot")
    fake_customer = stripe.Customer.construct_from(
        dict(
            object="customer",
            id="cus_Gz7jQFKdh4KirU",
            email="j.doe@example.com",
            balance=5000,
            created=1643455402,
        ),
        "fake-key",
    )
    customer_retrieve = mocker.patch(
        "core.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            default_payment_method="pm_47xubd3i",
            plan=dict(id="plan_Gz345gdsdf", amount=499),
            quantity=10,
            start_date=1443556775,
            current_period_start=1653173784,
            current_period_end=1660949784,
        ),
        "fake-key",
    )
    subscription_retrieve = mocker.patch(
        "core.views.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    fake_payment_method = stripe.PaymentMethod.construct_from(
        dict(
            object="payment_method",
            id="pm_55yfgbc6",
            card=dict(brand="mastercard", exp_month="04", exp_year="22", last4="4040"),
        ),
        "fake-key",
    )
    payment_method_retrieve = mocker.patch(
        "core.views.stripe.PaymentMethod.retrieve", return_value=fake_payment_method,
    )

    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login="acme-corp",
        github_account_type="User",
        stripe_customer_id="cus_Gz7jQFKdh4KirU",
    )
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
        subscription_current_period_start=1650581784,
        subscription_current_period_end=1658357784,
    )
    assert StripeCustomerInformation.objects.count() == 1
    res = post_webhook(
        """
{
  "id": "evt_1GTJLPCoyKa1V9Y6dIfvIuva",
  "object": "event",
  "api_version": "2020-03-02",
  "created": 1585796631,
  "data": {
    "object": {
      "id": "cs_test_Enc3u2mzp4vowbDcwrSneOhGOLwoYHX4UJGmUh6f4b3fnS88LTZgsJZT",
      "object": "checkout.session",
      "billing_address_collection": null,
      "cancel_url": "http://app.localhost.kodiakhq.com:3000/t/8f5b095f-9a11-4183-aa00-2152e2001a34/usage?start_subscription=1",
      "client_reference_id": "%s",
      "customer": "%s",
      "customer_email": null,
      "display_items": [
      ],
      "livemode": false,
      "locale": null,
      "metadata": {
      },
      "mode": "setup",
      "payment_intent": null,
      "payment_method_types": [
        "card"
      ],
      "setup_intent": "seti_1GTJKRCoyKa1V9Y6M41eERR5",
      "shipping": null,
      "shipping_address_collection": null,
      "submit_type": null,
      "subscription": null,
      "success_url": "http://app.localhost.kodiakhq.com:3000/t/8f5b095f-9a11-4183-aa00-2152e2001a34/usage?install_complete=1"
    }
  },
  "livemode": false,
  "pending_webhooks": 1,
  "request": {
    "id": null,
    "idempotency_key": null
  },
  "type": "checkout.session.completed"
}
"""
        % (account.id, account.stripe_customer_id)
    )
    assert res.status_code == 200
    assert customer_retrieve.call_count == 1
    assert subscription_retrieve.call_count == 1
    assert payment_method_retrieve.call_count == 1
    assert StripeCustomerInformation.objects.count() == 1

    assert update_bot.call_count == 1

    stripe_customer_info_updated = StripeCustomerInformation.objects.get()
    assert stripe_customer_info_updated.subscription_id == fake_subscription.id
    assert stripe_customer_info_updated.plan_id == fake_subscription.plan.id
    assert stripe_customer_info_updated.payment_method_id == fake_payment_method.id
    assert stripe_customer_info_updated.customer_email == fake_customer.email
    assert stripe_customer_info_updated.customer_balance == fake_customer.balance
    assert stripe_customer_info_updated.customer_created == fake_customer.created

    assert (
        stripe_customer_info_updated.payment_method_card_brand
        == fake_payment_method.card.brand
    )
    assert (
        stripe_customer_info_updated.payment_method_card_exp_month
        == fake_payment_method.card.exp_month
    )
    assert (
        stripe_customer_info_updated.payment_method_card_exp_year
        == fake_payment_method.card.exp_year
    )
    assert (
        stripe_customer_info_updated.payment_method_card_last4
        == fake_payment_method.card.last4
    )
    assert stripe_customer_info_updated.plan_amount == fake_subscription.plan.amount
    assert (
        stripe_customer_info_updated.subscription_quantity == fake_subscription.quantity
    )
    assert (
        stripe_customer_info_updated.subscription_start_date
        == fake_subscription.start_date
    )
    assert (
        stripe_customer_info_updated.subscription_current_period_end
        == fake_subscription.current_period_end
    )
    assert (
        stripe_customer_info_updated.subscription_current_period_start
        == fake_subscription.current_period_start
    )


def equal_subscriptions(
    a: StripeCustomerInformation, b: StripeCustomerInformation
) -> bool:
    for field_name in (
        field.attname for field in StripeCustomerInformation._meta.fields
    ):
        if getattr(a, field_name) != getattr(b, field_name):
            return False
    return True


@pytest.mark.django_db
def test_stripe_webhook_handler_checkout_session_complete_subscription(
    mocker: Any,
) -> None:
    """
    Verify our webhook handler creates a subscription on this event.
    """
    update_bot = mocker.patch("core.models.Account.update_bot")
    fake_customer = stripe.Customer.construct_from(
        dict(
            object="customer",
            id="cus_Gz7jQFKdh4KirU",
            email="j.doe@example.com",
            balance=5000,
            created=1643455402,
        ),
        "fake-key",
    )
    customer_retrieve = mocker.patch(
        "core.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            default_payment_method="pm_47xubd3i",
            plan=dict(id="plan_Gz345gdsdf", amount=499),
            quantity=10,
            start_date=1443556775,
            current_period_start=1653173784,
            current_period_end=1660949784,
        ),
        "fake-key",
    )
    subscription_retrieve = mocker.patch(
        "core.views.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    fake_payment_method = stripe.PaymentMethod.construct_from(
        dict(
            object="payment_method",
            id="pm_55yfgbc6",
            card=dict(brand="mastercard", exp_month="04", exp_year="22", last4="4040"),
        ),
        "fake-key",
    )
    payment_method_retrieve = mocker.patch(
        "core.views.stripe.PaymentMethod.retrieve", return_value=fake_payment_method,
    )

    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login="acme-corp",
        github_account_type="User",
        stripe_customer_id="",
    )
    other_account = Account.objects.create(
        github_installation_id=523940,
        github_account_id=65234234,
        github_account_login="delos-engineering",
        github_account_type="Organization",
        stripe_customer_id="cus_354HjLriodop21",
    )
    other_subscription = StripeCustomerInformation.objects.create(
        customer_id=other_account.stripe_customer_id,
        subscription_id="sub_L43DyAEVGwzt32",
        plan_id="plan_Gz345gdsdf",
        payment_method_id="pm_34lbsdf3",
        customer_email="engineering@delos.com",
        customer_balance=0,
        customer_created=1585781308,
        payment_method_card_brand="mastercard",
        payment_method_card_exp_month="03",
        payment_method_card_exp_year="32",
        payment_method_card_last4="4242",
        plan_amount=499,
        subscription_quantity=3,
        subscription_start_date=1585781784,
        subscription_current_period_start=1650581784,
        subscription_current_period_end=1658357784,
    )
    assert StripeCustomerInformation.objects.count() == 1
    assert update_bot.call_count == 0
    res = post_webhook(
        """
{
  "id": "evt_1GQQCUCoyKa1V9Y6EvAMbLgM",
  "object": "event",
  "api_version": "2020-03-02",
  "created": 1585108002,
  "data": {
    "object": {
      "id": "cs_test_3UbqT95rC08iaEzKbGT5tkYgLwuoEeUFfd93uiFaQoo9ZeslGZeV27fP",
      "object": "checkout.session",
      "billing_address_collection": null,
      "cancel_url": "http://app.localhost.kodiakhq.com:3000/t/8f5b095f-9a11-4183-aa00-2152e2001a34/usage?cancel=1",
      "client_reference_id": "%s",
      "customer": "cus_Gz7jQFKdh4KirU",
      "customer_email": null,
      "display_items": [
        {
          "amount": 499,
          "currency": "usd",
          "plan": {
            "id": "plan_GuzDf41AmGOJzQ",
            "object": "plan",
            "active": true,
            "aggregate_usage": null,
            "amount": 499,
            "amount_decimal": "499",
            "billing_scheme": "per_unit",
            "created": 1584327811,
            "currency": "usd",
            "interval": "month",
            "interval_count": 1,
            "livemode": false,
            "metadata": {
            },
            "nickname": "Monthly",
            "product": "prod_GuzCMVKonQIp2l",
            "tiers": null,
            "tiers_mode": null,
            "transform_usage": null,
            "trial_period_days": null,
            "usage_type": "licensed"
          },
          "quantity": 2,
          "type": "plan"
        }
      ],
      "livemode": false,
      "locale": null,
      "metadata": {
      },
      "mode": "subscription",
      "payment_intent": null,
      "payment_method_types": [
        "card"
      ],
      "setup_intent": null,
      "shipping": null,
      "shipping_address_collection": null,
      "submit_type": null,
      "subscription": "sub_GyMw1lyNB2LXmn",
      "success_url": "http://app.localhost.kodiakhq.com:3000/t/8f5b095f-9a11-4183-aa00-2152e2001a34/usage?success=1"
    }
  },
  "livemode": false,
  "pending_webhooks": 1,
  "request": {
    "id": "req_nIsiFwPHQZauDS",
    "idempotency_key": null
  },
  "type": "checkout.session.completed"
}"""
        % account.id
    )

    assert res.status_code == 200
    assert update_bot.call_count == 1
    assert customer_retrieve.call_count == 1
    assert subscription_retrieve.call_count == 1
    assert payment_method_retrieve.call_count == 1
    assert StripeCustomerInformation.objects.count() == 2

    # verify `other_subscription` hasn't been modified
    other_subscription_refreshed = StripeCustomerInformation.objects.filter(
        subscription_id=other_subscription.subscription_id
    ).get()
    assert equal_subscriptions(other_subscription_refreshed, other_subscription) is True

    stripe_customer_info_updated = StripeCustomerInformation.objects.filter(
        customer_id="cus_Gz7jQFKdh4KirU"
    ).get()
    assert stripe_customer_info_updated.subscription_id == fake_subscription.id
    assert stripe_customer_info_updated.plan_id == fake_subscription.plan.id
    assert stripe_customer_info_updated.payment_method_id == fake_payment_method.id
    assert stripe_customer_info_updated.customer_email == fake_customer.email
    assert stripe_customer_info_updated.customer_balance == fake_customer.balance
    assert stripe_customer_info_updated.customer_created == fake_customer.created

    assert (
        stripe_customer_info_updated.payment_method_card_brand
        == fake_payment_method.card.brand
    )
    assert (
        stripe_customer_info_updated.payment_method_card_exp_month
        == fake_payment_method.card.exp_month
    )
    assert (
        stripe_customer_info_updated.payment_method_card_exp_year
        == fake_payment_method.card.exp_year
    )
    assert (
        stripe_customer_info_updated.payment_method_card_last4
        == fake_payment_method.card.last4
    )
    assert stripe_customer_info_updated.plan_amount == fake_subscription.plan.amount
    assert (
        stripe_customer_info_updated.subscription_quantity == fake_subscription.quantity
    )
    assert (
        stripe_customer_info_updated.subscription_start_date
        == fake_subscription.start_date
    )
    assert (
        stripe_customer_info_updated.subscription_current_period_end
        == fake_subscription.current_period_end
    )
    assert (
        stripe_customer_info_updated.subscription_current_period_start
        == fake_subscription.current_period_start
    )


@pytest.mark.django_db
def test_stripe_webhook_handler_invoice_payment_succeeded(mocker: Any) -> None:
    """
    Verify our webhook handler updates our subscription on this event.

    This event will get sent when a subscription is updated.
    """
    update_bot = mocker.patch("core.models.Account.update_bot")
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login="acme-corp",
        github_account_type="User",
        stripe_customer_id="cus_523405923045",
    )

    stripe_customer_info = StripeCustomerInformation.objects.create(
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
        subscription_current_period_start=1590982549,
        subscription_current_period_end=1588304149,
    )
    fake_subscription = stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            current_period_end=1690982549,
            current_period_start=1688304149,
            items=dict(data=[dict(object="subscription_item", id="si_Gx234091sd2")]),
            plan=dict(id="plan_G2df31A4G5JzQ", object="plan", amount=499,),
            quantity=4,
            default_payment_method="pm_22dldxf3",
        ),
        "fake-key",
    )
    retrieve_subscription = mocker.patch(
        "core.views.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    update_bot = mocker.patch("core.models.Account.update_bot")
    assert StripeCustomerInformation.objects.count() == 1
    assert update_bot.call_count == 0
    assert retrieve_subscription.call_count == 0
    res = post_webhook(
        """
{
  "created": 1326853478,
  "livemode": false,
  "id": "evt_00000000000000",
  "type": "invoice.payment_succeeded",
  "object": "event",
  "request": null,
  "pending_webhooks": 1,
  "api_version": "2020-03-02",
  "data": {
    "object": {
      "id": "in_00000000000000",
      "object": "invoice",
      "account_country": "US",
      "account_name": "Kodiakhq",
      "amount_due": 9980,
      "amount_paid": 9980,
      "amount_remaining": 0,
      "application_fee_amount": null,
      "attempt_count": 1,
      "attempted": true,
      "auto_advance": false,
      "billing_reason": "subscription_create",
      "charge": "_00000000000000",
      "collection_method": "charge_automatically",
      "created": 1584328318,
      "currency": "usd",
      "custom_fields": null,
      "customer": "%s",
      "customer_address": null,
      "customer_email": "j.doe@example.com",
      "customer_name": null,
      "customer_phone": null,
      "customer_shipping": null,
      "customer_tax_exempt": "none",
      "customer_tax_ids": [
      ],
      "default_payment_method": null,
      "default_source": null,
      "default_tax_rates": [
      ],
      "description": null,
      "discount": null,
      "due_date": null,
      "ending_balance": 0,
      "footer": null,
      "hosted_invoice_url": "https://pay.stripe.com/invoice/acct_1GN6r2CoyKa1V9Y6/invst_GuzL5pfiHFXemcitpnDzhVLbrgrHk3T",
      "invoice_pdf": "https://pay.stripe.com/invoice/acct_1GN6r2CoyKa1V9Y6/invst_GuzL5pfiHFXemcitpnDzhVLbrgrHk3T/pdf",
      "lines": {
        "data": [
          {
            "id": "il_00000000000000",
            "object": "line_item",
            "amount": 4990,
            "currency": "usd",
            "description": "10 seat × Kodiak Seat License (at $4.99 / month)",
            "discountable": true,
            "livemode": false,
            "metadata": {
            },
            "period": {
              "end": 1660949784,
              "start": 1653173784
            },
            "plan": {
              "id": "plan_00000000000000",
              "object": "plan",
              "active": true,
              "aggregate_usage": null,
              "amount": 499,
              "amount_decimal": "499",
              "billing_scheme": "per_unit",
              "created": 1584327811,
              "currency": "usd",
              "interval": "month",
              "interval_count": 1,
              "livemode": false,
              "metadata": {
              },
              "nickname": "Monthly",
              "product": "prod_00000000000000",
              "tiers": null,
              "tiers_mode": null,
              "transform_usage": null,
              "trial_period_days": null,
              "usage_type": "licensed"
            },
            "proration": false,
            "quantity": 10,
            "subscription": "sub_00000000000000",
            "subscription_item": "si_00000000000000",
            "tax_amounts": [
            ],
            "tax_rates": [
            ],
            "type": "subscription"
          }
        ],
        "has_more": false,
        "object": "list",
        "url": "/v1/invoices/in_1GN9MwCoyKa1V9Y6Ox2tehjN/lines"
      },
      "livemode": false,
      "metadata": {
      },
      "next_payment_attempt": null,
      "number": "E5700931-0001",
      "paid": true,
      "payment_intent": "pi_00000000000000",
      "period_end": 1660949784,
      "period_start": 1653173784,
      "post_payment_credit_notes_amount": 0,
      "pre_payment_credit_notes_amount": 0,
      "receipt_number": "2421-2035",
      "starting_balance": 0,
      "statement_descriptor": null,
      "status": "paid",
      "status_transitions": {
        "finalized_at": 1584328319,
        "marked_uncollectible_at": null,
        "paid_at": 1584328320,
        "voided_at": null
      },
      "subscription": "sub_00000000000000",
      "subtotal": 9980,
      "tax": null,
      "tax_percent": null,
      "total": 9980,
      "total_tax_amounts": [
      ],
      "webhooks_delivered_at": 1584328320,
      "closed": true
    }
  }
}"""
        % account.stripe_customer_id
    )

    assert res.status_code == 200
    assert update_bot.call_count == 1
    assert retrieve_subscription.call_count == 1
    assert StripeCustomerInformation.objects.count() == 1
    updated_stripe_customer_info = StripeCustomerInformation.objects.get()
    assert (
        updated_stripe_customer_info.subscription_current_period_start
        > stripe_customer_info.subscription_current_period_start
    )
    assert (
        updated_stripe_customer_info.subscription_current_period_end
        > stripe_customer_info.subscription_current_period_end
    )
    assert updated_stripe_customer_info.subscription_current_period_end == 1690982549
    assert updated_stripe_customer_info.subscription_current_period_start == 1688304149


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
