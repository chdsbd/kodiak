import datetime
import json
import time
from typing import Any, Dict, Generator, Iterator, Optional, Tuple, Type, Union

import pytest
import responses
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from redis import Redis
from typing_extensions import Literal

from web_api.models import (
    Account,
    AccountMembership,
    AccountType,
    PullRequestActivity,
    StripeCustomerInformation,
    User,
    UserPullRequestActivity,
)
from web_api.testutils import TestClient as Client


@pytest.fixture
def user() -> User:
    return User.objects.create(
        github_id=10137,
        github_login="ghost",
        github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
    )


@pytest.fixture
def other_user() -> User:
    return User.objects.create(
        github_id=67647,
        github_login="bear",
        github_access_token="D2F92D26-BC64-427C-93CC-13E7110F3EB7",
    )


PRIMARY_KEYS = iter(range(1000, 100000))


def create_pk() -> int:
    return next(PRIMARY_KEYS)


def create_account(
    *,
    stripe_customer_id: str = "cus_523405923045",
    github_account_login: str = "acme-corp",
    github_account_type: Literal["User", "Organization"] = "User",
) -> Account:

    return Account.objects.create(
        github_installation_id=create_pk(),
        github_account_id=create_pk(),
        github_account_login=github_account_login,
        github_account_type=github_account_type,
        stripe_customer_id=stripe_customer_id,
    )


def create_org_account(
    user: User,
    role: Literal["member", "admin"] = "member",
    limit_billing_access_to_owners: bool = False,
) -> Tuple[Account, AccountMembership]:
    account_id = create_pk()
    account = Account.objects.create(
        github_installation_id=create_pk(),
        github_account_id=account_id,
        github_account_login=f"Acme-corp-{account_id}",
        github_account_type="Organization",
        stripe_customer_id=f"cus_Ged32s2xnx12-{account_id}",
        limit_billing_access_to_owners=limit_billing_access_to_owners,
    )
    membership = AccountMembership.objects.create(account=account, user=user, role=role)
    return (account, membership)


def create_stripe_customer_info(
    customer_id: str = "cus_eG4134df",
    subscription_id: str = "sub_Gu1xedsfo1",
    subscription_current_period_start: int = 1650581784,
    subscription_current_period_end: int = 1658357784,
) -> StripeCustomerInformation:
    return StripeCustomerInformation.objects.create(
        customer_id=customer_id,
        subscription_id=subscription_id,
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
        plan_interval="month",
        subscription_quantity=3,
        subscription_start_date=1585781784,
        subscription_current_period_start=subscription_current_period_start,
        subscription_current_period_end=subscription_current_period_end,
    )


def create_stripe_payment_method() -> stripe.PaymentMethod:
    return stripe.PaymentMethod.construct_from(
        dict(
            object="payment_method",
            id="pm_55yfgbc6",
            card=dict(brand="mastercard", exp_month="04", exp_year="22", last4="4040"),
        ),
        "fake-key",
    )


class Unset:
    pass


def create_stripe_customer(
    *,
    id: str = "cus_Gz7jQFKdh4KirU",
    address: Optional[Union[Dict[str, Any], Type[Unset]]] = Unset,
) -> stripe.Customer:
    if address == Unset:
        address = dict(
            line1="123 Main St",
            line2="Apt 2B",
            city="Cambridge",
            state="Massachusetts",
            postal_code="02139",
            country="United States",
        )
    return stripe.Customer.construct_from(
        dict(
            object="customer",
            id=id,
            address=address,
            balance=0,
            created=1592096376,
            currency="usd",
            email="accounting@acme.corp",
            name="Acme Corp Inc",
            subscriptions=dict(data=[dict(id="sub_Gu1xedsfo1")]),
        ),
        "fake-key",
    )


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
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
    user_account = create_account(github_account_login=user.github_login,)
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    today = datetime.datetime.now(timezone.utc)
    two_days_from_today = today + datetime.timedelta(days=2)

    # this user opened a PR on a private repository that Kodiak also acted on,
    # so we should count it.
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login=user.github_login,
        github_user_id=user.github_id,
        is_private_repository=True,
        activity_date=today,
        opened_pull_request=True,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=642,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=True,
        activity_date=today,
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
        activity_date=two_days_from_today,
        opened_pull_request=False,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=864,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=True,
        activity_date=today,
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
        activity_date=two_days_from_today,
        opened_pull_request=True,
    )
    UserPullRequestActivity.objects.create(
        github_installation_id=user_account.github_installation_id,
        github_repository_name="acme-web",
        github_pull_request_number=755,
        github_user_login="kodiakhq[bot]",
        github_user_id=11479,
        is_private_repository=False,
        activity_date=today,
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
        activity_date=two_days_from_today,
        opened_pull_request=True,
    )

    res = authed_client.get(f"/v1/t/{user_account.id}/usage_billing")
    assert res.status_code == 200
    assert (
        res.json()["accountCanSubscribe"] is False
    ), "user accounts should not see subscription options"
    today_str = today.strftime("%Y-%m-%d")
    assert res.json()["activeUsers"] == [
        dict(
            id=user.github_id,
            name=user.github_login,
            profileImgUrl=user.profile_image(),
            interactions=1,
            firstActiveDate=today_str,
            lastActiveDate=today_str,
            hasSeatLicense=False,
        )
    ]
    assert (
        res.json()["subscriptionExemption"] is None
    ), "we should always return this field"

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
    user_account = create_account(github_account_login=user.github_login,)
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
    user_account = create_account(github_account_login=user.github_login,)
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
    user_account = create_account(github_account_login=other_user.github_login,)
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
    mocker.patch(
        "web_api.models.time.time", return_value=period_start + 5 * ONE_DAY_SEC
    )
    account = create_account(
        github_account_login=user.github_login, stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")
    stripe_customer_information = create_stripe_customer_info(
        customer_id=account.stripe_customer_id,
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
    assert res.json()["subscription"]["cost"]["currency"] == "usd"
    assert res.json()["subscription"]["cost"]["planInterval"] == "month"
    assert res.json()["subscription"]["billingEmail"] == "accounting@acme-corp.com"
    assert res.json()["subscription"]["contactEmails"] == ""
    assert res.json()["subscription"]["cardInfo"] == "Mastercard (4242)"
    assert res.json()["subscription"]["customerName"] is None
    assert res.json()["subscription"]["customerAddress"] is None

    stripe_customer_information.customer_currency = None
    stripe_customer_information.plan_interval = "year"
    stripe_customer_information.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert (
        res.json()["subscription"]["cost"]["currency"] == "usd"
    ), "should default to usd if we cannot find a currency"
    assert res.json()["subscription"]["cost"]["planInterval"] == "year"

    stripe_customer_information.customer_name = "Acme-corp"
    stripe_customer_information.customer_address_line1 = "123 Main Street"
    stripe_customer_information.customer_address_city = "Anytown"
    stripe_customer_information.customer_address_country = "United States"
    stripe_customer_information.customer_address_line2 = "Apt B"
    stripe_customer_information.customer_address_postal_code = "02134"
    stripe_customer_information.customer_address_state = "Massachusetts"
    stripe_customer_information.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscription"]["customerName"] == "Acme-corp"
    assert res.json()["subscription"]["customerAddress"] == dict(
        line1=stripe_customer_information.customer_address_line1,
        city=stripe_customer_information.customer_address_city,
        country=stripe_customer_information.customer_address_country,
        line2=stripe_customer_information.customer_address_line2,
        postalCode=stripe_customer_information.customer_address_postal_code,
        state=stripe_customer_information.customer_address_state,
    )


@pytest.mark.django_db
def test_usage_limit_billing_access_to_owners_member(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    account, membership = create_org_account(user=user, role="member")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscription"] is not None
    assert res.json()["subscription"]["viewerIsOrgOwner"] is False
    assert res.json()["subscription"]["viewerCanModify"] is True
    assert res.json()["subscription"]["limitBillingAccessToOwners"] is False

    account.limit_billing_access_to_owners = True
    account.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscription"] is not None
    assert res.json()["subscription"]["viewerIsOrgOwner"] is False
    assert res.json()["subscription"]["viewerCanModify"] is False
    assert res.json()["subscription"]["limitBillingAccessToOwners"] is True

    membership.role = "admin"
    membership.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscription"] is not None
    assert res.json()["subscription"]["viewerIsOrgOwner"] is True
    assert res.json()["subscription"]["viewerCanModify"] is True
    assert res.json()["subscription"]["limitBillingAccessToOwners"] is True


@pytest.mark.django_db
def test_usage_billing_subscription_exemption(
    authed_client: Client, user: User
) -> None:
    """
    When a subscription exemption is enabled we'll return a null message unless
    one is specified.

    We shouldn't be able to subscribe with an exemption
    """
    account, membership = create_org_account(user=user, role="member")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)

    account.subscription_exempt = True
    account.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscriptionExemption"] == dict(message=None)
    assert res.json()["accountCanSubscribe"] is False

    account.subscription_exempt = True
    account.subscription_exempt_message = (
        "As a GitHub Sponsor of Kodiak you have complimentary access."
    )
    account.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
    assert res.json()["subscriptionExemption"] == dict(
        message=account.subscription_exempt_message
    )
    assert res.json()["accountCanSubscribe"] is False


@pytest.mark.django_db
def test_fetch_proration(authed_client: Client, user: User, mocker: Any) -> None:
    """
    Verify that our proration endpoint correctly handles proration.
    """
    account, _membership = create_org_account(user)
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    patched_stripe_subscription_retrieve = mocker.patch(
        "web_api.models.stripe.Subscription.retrieve",
        spec=stripe.Subscription.retrieve,
        return_value=create_stripe_subscription(),
    )
    fake_invoice = stripe.Invoice.construct_from(
        {
            "id": "in_1GN9MwCoyKa1V9Y6Ox2tehjN",
            "object": "invoice",
            "lines": {
                "data": [
                    {
                        "id": "il_tmp_aad05f08b40091",
                        "object": "line_item",
                        "amount": 4990,
                        "period": {"end": 1623632393, "start": 1592096393},
                    }
                ],
                "object": "list",
            },
        },
        "fake-key",
    )
    patched_stripe_invoice_upcoming = mocker.patch(
        "web_api.models.stripe.Invoice.upcoming",
        spec=stripe.Invoice.upcoming,
        return_value=fake_invoice,
    )
    res = authed_client.post(
        f"/v1/t/{account.id}/fetch_proration", {"subscriptionQuantity": 4}
    )
    assert res.status_code == 200
    assert res.json()["proratedCost"] == 4990
    assert isinstance(res.json()["prorationTime"], int)
    assert patched_stripe_subscription_retrieve.call_count == 1
    assert patched_stripe_invoice_upcoming.call_count == 1


@pytest.mark.django_db
def test_fetch_proration_different_plans(
    authed_client: Client, user: User, mocker: Any
) -> None:
    """
    Check support for different plans.
    """
    patched_stripe_customer_information = mocker.patch(
        "web_api.models.StripeCustomerInformation.preview_proration",
        spec=StripeCustomerInformation.preview_proration,
        return_value=4567,
    )
    account, _membership = create_org_account(user)
    create_stripe_customer_info(customer_id=account.stripe_customer_id)

    # we should default to the "monthly" plan period.
    res = authed_client.post(
        f"/v1/t/{account.id}/fetch_proration", {"subscriptionQuantity": 4}
    )
    assert res.status_code == 200
    assert res.json()["proratedCost"] == 4567
    assert isinstance(res.json()["prorationTime"], int)
    assert patched_stripe_customer_information.call_count == 1
    _args, kwargs = patched_stripe_customer_information.call_args
    assert kwargs["subscription_quantity"] == 4
    assert kwargs["plan_id"] == settings.STRIPE_PLAN_ID

    # verify we respect the `subscriptionPeriod` argument for proration.
    for index, period_plan in enumerate(
        [("year", settings.STRIPE_ANNUAL_PLAN_ID), ("month", settings.STRIPE_PLAN_ID)]
    ):
        period, plan = period_plan
        seats = index + 5
        res = authed_client.post(
            f"/v1/t/{account.id}/fetch_proration",
            {"subscriptionQuantity": seats, "subscriptionPeriod": period},
        )
        assert res.status_code == 200
        assert res.json()["proratedCost"] == 4567
        _args, kwargs = patched_stripe_customer_information.call_args
        assert kwargs["subscription_quantity"] == seats
        assert kwargs["plan_id"] == plan
        assert patched_stripe_customer_information.call_count == index + 2


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
    update_bot = mocker.patch("web_api.models.Account.update_bot")

    fake_subscription = create_stripe_subscription()
    stripe_subscription_retrieve = mocker.patch(
        "web_api.models.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    stripe_subscription_modify = mocker.patch(
        "web_api.models.stripe.Subscription.modify", return_value=fake_subscription
    )
    fake_invoice = stripe.Invoice.construct_from(
        dict(object="invoice", id="in_00000000000000"), "fake-key",
    )
    stripe_invoice_create = mocker.patch(
        "web_api.models.stripe.Invoice.create", return_value=fake_invoice
    )
    stripe_invoice_pay = mocker.patch("web_api.models.stripe.Invoice.pay")
    assert user.github_login is not None
    account = create_account(
        github_account_login=user.github_login, stripe_customer_id="cus_Ged32s2xnx12",
    )
    AccountMembership.objects.create(account=account, user=user, role="admin")
    create_stripe_customer_info(
        customer_id=account.stripe_customer_id,
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
    _args, kwargs = stripe_subscription_modify.call_args
    assert kwargs["items"][0]["plan"] == settings.STRIPE_PLAN_ID
    assert stripe_invoice_create.call_count == 1
    assert stripe_invoice_pay.call_count == 1

    # verify we can specify the monthly planPeriod and that the API calls Stripe
    # with the correct plan id.
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(
            prorationTimestamp=period_start + 4 * ONE_DAY_SEC,
            seats=8,
            planPeriod="month",
        ),
    )
    assert res.status_code == 204
    assert stripe_subscription_retrieve.call_count == 2
    assert update_bot.call_count == 2
    assert stripe_subscription_modify.call_count == 2
    _args, kwargs = stripe_subscription_modify.call_args
    assert kwargs["items"][0]["plan"] == settings.STRIPE_PLAN_ID
    assert stripe_invoice_create.call_count == 2
    assert stripe_invoice_pay.call_count == 2

    # verify we can specify the yearly planPeriod and that the API calls Stripe
    # with the correct plan id.
    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(
            prorationTimestamp=period_start + 4 * ONE_DAY_SEC,
            seats=4,
            planPeriod="year",
        ),
    )
    assert res.status_code == 204
    assert stripe_subscription_retrieve.call_count == 3
    assert update_bot.call_count == 3
    assert stripe_subscription_modify.call_count == 3
    _args, kwargs = stripe_subscription_modify.call_args
    assert kwargs["items"][0]["plan"] == settings.STRIPE_ANNUAL_PLAN_ID
    assert stripe_invoice_create.call_count == 2, "not hit because we're changing plans"
    assert stripe_invoice_pay.call_count == 2, "not hit because we're changing plans"


def create_stripe_subscription(
    interval: Literal["month", "year"] = "month"
) -> stripe.Subscription:
    return stripe.Subscription.construct_from(
        dict(
            object="subscription",
            id="sub_Gu1xedsfo1",
            current_period_end=1690982549,
            current_period_start=1688304149,
            items=dict(data=[dict(object="subscription_item", id="si_Gx234091sd2")]),
            plan=dict(
                id=settings.STRIPE_ANNUAL_PLAN_ID,
                object="plan",
                amount=499,
                interval=interval,
                interval_count=1,
            ),
            quantity=4,
            start_date=1443556775,
            default_payment_method="pm_22dldxf3",
        ),
        "fake-key",
    )


@pytest.mark.django_db
def test_update_subscription_switch_plans(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    When we switch between plans we do _not_ want to manually create an invoice
    because Stripe already charges the user. If we attempt to invoice like we do
    for intra-plan upgrades we'll get an API exception from Stripe saying
    nothing to change.
    """
    update_bot = mocker.patch("web_api.models.Account.update_bot")

    stripe_subscription_retrieve = mocker.patch(
        "web_api.models.stripe.Subscription.retrieve",
        return_value=create_stripe_subscription(interval="month"),
    )
    stripe_subscription_modify = mocker.patch(
        "web_api.models.stripe.Subscription.modify",
        return_value=create_stripe_subscription(interval="year"),
    )
    fake_invoice = stripe.Invoice.construct_from(
        dict(object="invoice", id="in_00000000000000"), "fake-key",
    )
    stripe_invoice_create = mocker.patch(
        "web_api.models.stripe.Invoice.create", return_value=fake_invoice
    )
    stripe_invoice_pay = mocker.patch("web_api.models.stripe.Invoice.pay")
    account, _membership = create_org_account(user=user, role="admin")
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    assert stripe_subscription_retrieve.call_count == 0
    assert stripe_subscription_modify.call_count == 0
    assert update_bot.call_count == 0
    assert stripe_customer_info.plan_interval == "month"

    res = authed_client.post(
        f"/v1/t/{account.id}/update_subscription",
        dict(prorationTimestamp=123456789, seats=4, planPeriod="year"),
    )
    assert res.status_code == 204
    assert stripe_subscription_retrieve.call_count == 1
    assert update_bot.call_count == 1
    assert stripe_subscription_modify.call_count == 1
    _args, kwargs = stripe_subscription_modify.call_args
    assert kwargs["items"][0]["plan"] == settings.STRIPE_ANNUAL_PLAN_ID
    assert stripe_invoice_create.call_count == 0, "not hit because we're changing plans"
    assert stripe_invoice_pay.call_count == 0, "not hit because we're changing plans"
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.plan_interval == "year"


@pytest.mark.django_db
def test_update_subscription_missing_customer(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    We should get an error when we try to update a subscription for an Account
    that doesn't have an associated subscription.
    """
    fake_subscription = create_stripe_subscription()

    stripe_subscription_retrieve = mocker.patch(
        "web_api.models.stripe.Subscription.retrieve", return_value=fake_subscription
    )
    stripe_subscription_modify = mocker.patch(
        "web_api.models.stripe.Subscription.modify", return_value=fake_subscription
    )
    assert user.github_login is not None
    account = create_account(
        github_account_login=user.github_login, stripe_customer_id="cus_Ged32s2xnx12",
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
def test_update_subscription_permissions(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    By default any member can edit a subscription, but if
    `limit_billing_access_to_owners` is enabled on an account, only admins a.k.a
    owners can modify a subscription.
    """
    account, membership = create_org_account(user=user, role="member")
    payload = dict(prorationTimestamp=1650581784, seats=24)
    res = authed_client.post(f"/v1/t/{account.id}/update_subscription", payload,)
    assert (
        res.status_code == 422
    ), "we get a 422 because the account doesn't have a corresponding Stripe model. This is okay."

    account.limit_billing_access_to_owners = True
    account.save()
    res = authed_client.post(f"/v1/t/{account.id}/update_subscription", payload,)
    assert res.status_code == 403, "we're a member so we shouldn't be allowed"

    membership.role = "admin"
    membership.save()
    res = authed_client.post(f"/v1/t/{account.id}/update_subscription", payload,)
    assert res.status_code == 422, "we're an admin so we should be okay"


@pytest.mark.django_db
def test_cancel_subscription(
    authed_client: Client, user: User, other_user: User, mocker: Any
) -> None:
    """
    Canceling a subscription should immediately cancel the subscription in Stripe.
    """
    patched_stripe_subscription_delete = mocker.patch(
        "web_api.models.stripe.Subscription.delete"
    )
    patched_account_update_bot = mocker.patch("web_api.models.Account.update_bot")
    account, membership = create_org_account(user=user, role="admin")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    assert patched_stripe_subscription_delete.call_count == 0
    assert StripeCustomerInformation.objects.count() == 1
    assert patched_account_update_bot.call_count == 0
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 204
    assert patched_account_update_bot.call_count == 1
    assert patched_stripe_subscription_delete.call_count == 1
    assert StripeCustomerInformation.objects.count() == 0


@pytest.fixture
def patch_cancel_subscription(mocker: Any) -> None:
    mocker.patch("web_api.models.stripe.Subscription.delete")
    mocker.patch("web_api.models.Account.update_bot")


@pytest.mark.django_db
def test_cancel_subscription_member(
    authed_client: Client,
    user: User,
    other_user: User,
    patch_cancel_subscription: object,
) -> None:
    """
    By default all members can cancel a subscription.
    """
    account, membership = create_org_account(user=user, role="member")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    assert StripeCustomerInformation.objects.count() == 1
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 204
    assert StripeCustomerInformation.objects.count() == 0


@pytest.mark.django_db
def test_cancel_subscription_member_limit_billing_access_to_owners(
    authed_client: Client,
    user: User,
    other_user: User,
    patch_cancel_subscription: object,
) -> None:
    """
    If limit_billing_access_to_owners is enabled members cannot cancel a
    subscription.
    """
    account, membership = create_org_account(
        user=user, role="member", limit_billing_access_to_owners=True
    )
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    assert StripeCustomerInformation.objects.count() == 1
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 403
    assert StripeCustomerInformation.objects.count() == 1


@pytest.mark.django_db
def test_cancel_subscription_admin_limit_billing_access_to_owners(
    authed_client: Client,
    user: User,
    other_user: User,
    patch_cancel_subscription: object,
) -> None:
    """
    If limit_billing_access_to_owners is enabled admins can cancel a
    subscription.
    """
    account, membership = create_org_account(
        user=user, role="admin", limit_billing_access_to_owners=True
    )
    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    assert StripeCustomerInformation.objects.count() == 1
    res = authed_client.post(f"/v1/t/{account.id}/cancel_subscription")
    assert res.status_code == 204
    assert StripeCustomerInformation.objects.count() == 0


@pytest.mark.django_db
def test_activity(authed_client: Client, user: User,) -> None:
    assert user.github_login is not None
    user_account = create_account(github_account_login=user.github_login,)
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
    assert res.json()["activeMergeQueues"] == []


@pytest.fixture
def redis() -> Generator["Redis[bytes]", None, None]:
    """
    Fixture for using local Redis in tests. We clear the database before and
    after for cleanliness.
    """
    r = Redis(decode_responses=False)
    r.flushdb()
    yield r
    r.flushdb()


@pytest.mark.django_db
def test_activity_with_merge_queues(
    authed_client: Client, user: User, redis: "Redis[bytes]"
) -> None:
    """
    We should return active merge queues from Redis if available.
    """
    assert user.github_login is not None
    user_account = create_account(github_account_login=user.github_login,)
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    install_id = user_account.github_installation_id
    queue = f"merge_queue:{install_id}.sbdchd/squawk/main"
    empty_queue = f"merge_queue:{install_id}.sbdchd/time-to-deploy/main"
    redis.sadd(f"merge_queue_by_install:{install_id}", queue, empty_queue)
    merging_pr = (
        '{"repo_owner": "sbdchd", "repo_name": "squawk", "pull_request_number": 55, "installation_id": "%s", "target_name": "main"}'
        % install_id
    )
    redis.set(queue + ":target", merging_pr)
    waiting_pr = (
        '{"repo_owner": "sbdchd", "repo_name": "squawk", "pull_request_number": 57, "installation_id": "%s", "target_name": "main"}'
        % install_id
    )
    score = 1614997354.8109288
    redis.zadd(
        queue, {waiting_pr: score},
    )
    redis.zadd(
        queue, {merging_pr: score + 1000},
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 200
    assert res.json()["activeMergeQueues"] == [
        dict(
            owner="sbdchd",
            repo="squawk",
            queues=[
                dict(
                    branch="main",
                    pull_requests=[
                        dict(number="55", added_at_timestamp=None),
                        dict(number="57", added_at_timestamp=1614997354.8109288),
                    ],
                )
            ],
        )
    ]


@pytest.mark.django_db
def test_activity_with_merge_queues_invalid_parsing(
    authed_client: Client, user: User, redis: "Redis[bytes]"
) -> None:
    """
    We should ignore pull requests we can't parse so the web UI is robust.
    """
    assert user.github_login is not None
    user_account = create_account(github_account_login=user.github_login,)
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    install_id = user_account.github_installation_id
    queue = f"merge_queue:{install_id}.sbdchd/squawk/main"
    empty_queue = f"merge_queue:{install_id}.sbdchd/time-to-deploy/main"
    redis.sadd(f"merge_queue_by_install:{install_id}", queue, empty_queue)
    waiting_pr_with_invalid_stucture = (
        '{"repo_owner": "sbdchd", "repo_name": "squawk", "pull_request_number": 57, }'
    )
    redis.zadd(
        queue, {waiting_pr_with_invalid_stucture: 1614997354.8109288},
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/activity")
    assert res.status_code == 200
    assert res.json()["activeMergeQueues"] == []


@pytest.mark.django_db
def test_activity_authentication(authed_client: Client, other_user: User,) -> None:
    assert other_user.github_login is not None
    user_account = create_account(github_account_login=other_user.github_login,)
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
    assert user.github_login is not None
    user_account = create_account(github_account_login=user.github_login,)
    AccountMembership.objects.create(account=user_account, user=user, role="member")

    class FakeCheckoutSession:
        id = "cs_tgn3bJHRrXhqgdVSc4tsY"

    checkout_session_create = mocker.patch(
        "web_api.views.stripe.checkout.Session.create",
        spec=stripe.checkout.Session.create,
        return_value=FakeCheckoutSession,
    )

    # start checkout without a plan to check backwards compatibility. We should
    # default to using the monthly plan.
    res = authed_client.post(
        f"/v1/t/{user_account.id}/start_checkout", dict(seatCount=3)
    )
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY
    _args, kwargs = checkout_session_create.call_args
    assert kwargs["subscription_data"]["items"][0]["quantity"] == 3
    assert kwargs["subscription_data"]["items"][0]["plan"] == settings.STRIPE_PLAN_ID

    # start checkout with a monthly plan.
    res = authed_client.post(
        f"/v1/t/{user_account.id}/start_checkout", dict(seatCount=5, planPeriod="month")
    )
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY
    _args, kwargs = checkout_session_create.call_args
    assert kwargs["subscription_data"]["items"][0]["quantity"] == 5
    assert kwargs["subscription_data"]["items"][0]["plan"] == settings.STRIPE_PLAN_ID

    # start checkout with a yearly plan.
    res = authed_client.post(
        f"/v1/t/{user_account.id}/start_checkout", dict(seatCount=2, planPeriod="year")
    )
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY
    _args, kwargs = checkout_session_create.call_args
    assert kwargs["subscription_data"]["items"][0]["quantity"] == 2
    assert (
        kwargs["subscription_data"]["items"][0]["plan"]
        == settings.STRIPE_ANNUAL_PLAN_ID
    )


@pytest.mark.django_db
def test_modify_payment_details(authed_client: Client, user: User, mocker: Any) -> None:
    """
    Start a new checkout session in "setup" mode to update the payment information.
    """
    account, _membership = create_org_account(user=user, role="member",)

    class FakeCheckoutSession:
        id = "cs_tgn3bJHRrXhqgdVSc4tsY"

    mocker.patch(
        "web_api.views.stripe.checkout.Session.create", return_value=FakeCheckoutSession
    )
    res = authed_client.post(f"/v1/t/{account.id}/modify_payment_details")
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY


@pytest.mark.django_db
def test_modify_payment_details_limit_billing_access_to_owners(
    authed_client: Client, user: User, mocker: Any
) -> None:
    account, membership = create_org_account(
        user=user, role="member", limit_billing_access_to_owners=True
    )

    class FakeCheckoutSession:
        id = "cs_tgn3bJHRrXhqgdVSc4tsY"

    mocker.patch(
        "web_api.views.stripe.checkout.Session.create", return_value=FakeCheckoutSession
    )
    res = authed_client.post(f"/v1/t/{account.id}/modify_payment_details")
    assert res.status_code == 403

    membership.role = "admin"
    membership.save()
    res = authed_client.post(f"/v1/t/{account.id}/modify_payment_details")
    assert res.status_code == 200
    assert res.json()["stripeCheckoutSessionId"] == FakeCheckoutSession.id
    assert res.json()["stripePublishableApiKey"] == settings.STRIPE_PUBLISHABLE_API_KEY


@pytest.fixture
def patch_stripe_customer_modify(mocker: Any) -> None:
    mocker.patch("web_api.models.stripe.Customer.modify", spec=stripe.Customer.modify)


@pytest.mark.django_db
def test_update_stripe_customer_info_permission(
    authed_client: Client, user: User, patch_stripe_customer_modify: object
) -> None:
    account, membership = create_org_account(user, role="member")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)

    assert account.limit_billing_access_to_owners is False
    payload = dict(limitBillingAccessToOwners=True)
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 403
    account.refresh_from_db()
    assert account.limit_billing_access_to_owners is False

    membership.role = "admin"
    membership.save()
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    account.refresh_from_db()
    assert account.limit_billing_access_to_owners is True


@pytest.mark.django_db
def test_update_stripe_customer_info_limit_billing_access_to_owners(
    authed_client: Client, user: User, patch_stripe_customer_modify: object
) -> None:
    account, membership = create_org_account(user, role="member")
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )

    original_email = "invoices@acme-inc.corp"
    stripe_customer_info.customer_email = original_email
    stripe_customer_info.save()
    account.limit_billing_access_to_owners = True
    account.save()

    payload = dict(email="billing@kodiakhq.com")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 403
    account.refresh_from_db()
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_email == original_email

    membership.role = "admin"
    membership.save()
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    account.refresh_from_db()
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_email == payload["email"]


@pytest.mark.django_db
def test_update_billing_email(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    A user should be able to modifying billing email.
    """
    account, _membership = create_org_account(user)
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )

    stripe_customer_info.customer_email = "invoices@acme-inc.corp"
    stripe_customer_info.save()

    payload = dict(email="billing@kodiakhq.com")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_email == payload["email"]


@pytest.mark.django_db
def test_update_billing_email_empty(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    We should error if the user tries to update an email to empty string
    """
    account, _membership = create_org_account(user)
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )

    original_email = "invoices@acme-inc.corp"
    stripe_customer_info.customer_email = original_email
    stripe_customer_info.save()

    payload = dict(email="")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 400
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_email == original_email


@pytest.mark.django_db
def test_update_contact_emails(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    User should be able to set contact emails
    """
    account, membership = create_org_account(user)

    original_email = "j.doe@acme-inc.corp"
    account.contact_emails = original_email
    account.save()

    # by default a user should be able to set the contact emails fields.
    payload = dict(contactEmails="a.hamilton@treasury.gov\ng.washington@whitehouse.gov")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    account.refresh_from_db()
    assert account.contact_emails == payload["contactEmails"]

    # if we limit to billing access and the user is not an admin they should be
    # prevented from updating.
    account.limit_billing_access_to_owners = True
    account.save()

    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 403

    # an admin can set the field when limit_billing_access_to_owners is enabled.
    membership.role = "admin"
    membership.save()

    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204


@pytest.mark.django_db
def test_update_company_name(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    A user should be able to modify the company name.
    """
    account, _membership = create_org_account(user)
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )

    stripe_customer_info.customer_name = "Acme Corp Inc."
    stripe_customer_info.save()

    payload = dict(name="Kodiak Bait & Tackle")
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_name == payload["name"]


@pytest.mark.django_db
def test_update_address(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    A user should be able to modifying postal address.
    """
    account, _membership = create_org_account(user)
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )

    stripe_customer_info.customer_address_line1 = None
    stripe_customer_info.customer_address_city = None
    stripe_customer_info.customer_address_country = None
    stripe_customer_info.customer_address_line2 = None
    stripe_customer_info.customer_address_postal_code = None
    stripe_customer_info.customer_address_state = None
    stripe_customer_info.save()

    payload = dict(
        address=dict(
            line1="123 Main St",
            line2="Apt 3B",
            city="Anytown",
            postalCode="12345",
            state="Massachusetts",
            country="United States",
        )
    )
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_address_line1 == payload["address"]["line1"]
    assert stripe_customer_info.customer_address_city == payload["address"]["city"]
    assert (
        stripe_customer_info.customer_address_country == payload["address"]["country"]
    )
    assert stripe_customer_info.customer_address_line2 == payload["address"]["line2"]
    assert (
        stripe_customer_info.customer_address_postal_code
        == payload["address"]["postalCode"]
    )
    assert stripe_customer_info.customer_address_state == payload["address"]["state"]


@pytest.mark.django_db
def test_update_limit_billing_access_to_owners(
    authed_client: Client, user: User, mocker: Any, patch_stripe_customer_modify: object
) -> None:
    """
    Only GitHub organization Owners should be able to modify this field
    """
    account, membership = create_org_account(user, role="member")
    create_stripe_customer_info(customer_id=account.stripe_customer_id)

    payload = dict(limitBillingAccessToOwners=True)
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 403

    membership.role = "admin"
    membership.save()
    res = authed_client.post(
        f"/v1/t/{account.id}/update_stripe_customer_info",
        payload,
        content_type="application/json",
    )
    assert res.status_code == 204
    account.refresh_from_db()
    assert account.limit_billing_access_to_owners is True


@pytest.mark.django_db
def test_accounts_endpoint_ordering(authed_client: Client, user: User) -> None:
    """
    Ensure we order the accounts in the response by name.

    We could also sort them on the frontend.
    """
    industries = create_account(
        github_account_login="industries", github_account_type="Organization",
    )
    AccountMembership.objects.create(account=industries, user=user, role="member")

    acme = create_account(
        github_account_login="acme-corp", github_account_type="Organization",
    )
    AccountMembership.objects.create(account=acme, user=user, role="member")

    market = create_account(
        github_account_login="market", github_account_type="Organization",
    )
    AccountMembership.objects.create(account=market, user=user, role="member")

    res = authed_client.get("/v1/accounts")
    assert res.json() == [
        {
            "id": str(acme.id),
            "name": "acme-corp",
            "profileImgUrl": f"https://avatars.githubusercontent.com/u/{acme.github_account_id}",
        },
        {
            "id": str(industries.id),
            "name": "industries",
            "profileImgUrl": f"https://avatars.githubusercontent.com/u/{industries.github_account_id}",
        },
        {
            "id": str(market.id),
            "name": "market",
            "profileImgUrl": f"https://avatars.githubusercontent.com/u/{market.github_account_id}",
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
    assert user.github_login is not None
    user_account = create_account(github_account_login=user.github_login,)
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = create_account(
        github_account_login="recipeyak", github_account_type="Organization",
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
    accounts = sorted(res.json()["accounts"], key=lambda x: x["name"])  # type: ignore [no-any-return]
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
    assert other_user.github_login is not None
    user_account = create_account(github_account_login=other_user.github_login,)
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/current_account")
    assert res.status_code == 404


@pytest.mark.django_db
def test_accounts(authed_client: Client, user: User) -> None:
    assert user.github_login is not None
    user_account = create_account(
        github_account_login=user.github_login, github_account_type="User",
    )
    AccountMembership.objects.create(account=user_account, user=user, role="member")
    org_account = create_account(
        github_account_login="recipeyak", github_account_type="Organization",
    )
    AccountMembership.objects.create(account=org_account, user=user, role="member")

    res = authed_client.get("/v1/accounts")
    assert res.status_code == 200
    assert len(res.json()) == 2
    accounts = sorted(res.json(), key=lambda x: x["name"])  # type: ignore [no-any-return]
    assert accounts[0]["id"] == str(user_account.id)
    assert accounts[0]["name"] == user_account.github_account_login
    assert (
        accounts[0]["profileImgUrl"]
        == f"https://avatars.githubusercontent.com/u/{user_account.github_account_id}"
    )


@pytest.fixture
def patch_start_trial(mocker: Any) -> None:
    fake_customer = create_stripe_customer()
    mocker.patch("web_api.models.stripe.Customer.create", return_value=fake_customer)
    mocker.patch("web_api.models.stripe.Customer.modify", return_value=fake_customer)


@pytest.mark.django_db
def test_start_trial(
    authed_client: Client, user: User, patch_start_trial: object, mocker: Any
) -> None:
    """
    When a user starts a trial we should update their account.
    """
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    assert user.github_login is not None
    account = create_account(
        github_account_login=user.github_login, github_account_type="User",
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


def similar_dates(
    a: Optional[datetime.datetime], b: Optional[datetime.datetime]
) -> bool:
    """
    Dates are equal if they are within 5 minutes of each other. This should
    hopefully reduce flakiness is tests.
    """
    assert a is not None and b is not None
    return abs(int(a.timestamp()) - int(b.timestamp())) < 60 * 5


@pytest.mark.django_db
def test_start_trial_existing_trial(
    authed_client: Client, user: User, patch_start_trial: object
) -> None:
    """
    Starting a trial when there is already an existing trial shouldn't alter
    current trial.
    """
    assert user.github_login is not None
    account = create_account(
        github_account_login=user.github_login, github_account_type="User",
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


def post_webhook(event: Union[Dict[str, Any], str]) -> HttpResponse:
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
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    account = create_account()
    fake_customer = create_stripe_customer(id=account.stripe_customer_id, address=None)
    customer_retrieve = mocker.patch(
        "web_api.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    fake_subscription = create_stripe_subscription()
    subscription_retrieve = mocker.patch(
        "web_api.views.stripe.Subscription.retrieve", return_value=fake_subscription,
    )
    fake_payment_method = create_stripe_payment_method()
    payment_method_retrieve = mocker.patch(
        "web_api.views.stripe.PaymentMethod.retrieve", return_value=fake_payment_method,
    )

    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    assert StripeCustomerInformation.objects.count() == 1
    assert account.stripe_customer_info() == stripe_customer_info
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
    assert stripe_customer_info_updated.customer_currency == fake_customer.currency

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
        stripe_customer_info_updated.plan_interval_count
        == fake_subscription.plan.interval_count
    )
    assert stripe_customer_info_updated.plan_interval == fake_subscription.plan.interval
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
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    fake_customer = create_stripe_customer()
    customer_retrieve = mocker.patch(
        "web_api.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    fake_subscription = create_stripe_subscription()
    subscription_retrieve = mocker.patch(
        "web_api.views.stripe.Subscription.retrieve", return_value=fake_subscription,
    )
    fake_payment_method = create_stripe_payment_method()
    payment_method_retrieve = mocker.patch(
        "web_api.views.stripe.PaymentMethod.retrieve", return_value=fake_payment_method,
    )

    account = create_account(stripe_customer_id="")
    other_account = create_account(
        github_account_login="delos-engineering",
        github_account_type="Organization",
        stripe_customer_id="cus_354HjLriodop21",
    )
    other_subscription = create_stripe_customer_info(
        customer_id=other_account.stripe_customer_id,
        subscription_id="sub_L43DyAEVGwzt32",
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
        stripe_customer_info_updated.plan_interval_count
        == fake_subscription.plan.interval_count
    )
    assert stripe_customer_info_updated.plan_interval == fake_subscription.plan.interval
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
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    account = create_account()

    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    retrieve_customer = mocker.patch(
        "web_api.views.stripe.Customer.retrieve", return_value=create_stripe_customer(),
    )
    retrieve_subscription = mocker.patch(
        "web_api.views.stripe.Subscription.retrieve",
        return_value=create_stripe_subscription(),
    )
    retrieve_payment_method = mocker.patch(
        "web_api.views.stripe.PaymentMethod.retrieve",
        return_value=create_stripe_payment_method(),
    )
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    assert StripeCustomerInformation.objects.count() == 1
    assert update_bot.call_count == 0
    assert retrieve_subscription.call_count == 0
    assert retrieve_customer.call_count == 0
    assert retrieve_payment_method.call_count == 0
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
    assert retrieve_customer.call_count == 1
    assert retrieve_payment_method.call_count == 1
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


def make_customer_updated_event(customer_id: str) -> str:
    return (
        """
{
  "created": 1326853478,
  "livemode": false,
  "id": "evt_00000000000000",
  "type": "customer.updated",
  "object": "event",
  "request": null,
  "pending_webhooks": 1,
  "api_version": "2020-03-02",
  "data": {
    "object": {
      "id": "%s",
      "object": "customer",
      "address": null,
      "balance": 0,
      "created": 1592097133,
      "currency": "usd",
      "default_source": null,
      "delinquent": false,
      "description": null,
      "discount": null,
      "email": null,
      "invoice_prefix": "62BA0D0",
      "invoice_settings": {
        "custom_fields": null,
        "default_payment_method": null,
        "footer": null
      },
      "livemode": false,
      "metadata": {
      },
      "name": null,
      "next_invoice_sequence": 1,
      "phone": null,
      "preferred_locales": [
      ],
      "shipping": null,
      "sources": {
        "object": "list",
        "data": [
        ],
        "has_more": false,
        "url": "/v1/customers/cus_HSfjRanfIZeNYE/sources"
      },
      "subscriptions": {
        "object": "list",
        "data": [
        ],
        "has_more": false,
        "url": "/v1/customers/cus_HSfjRanfIZeNYE/subscriptions"
      },
      "tax_exempt": "none",
      "tax_ids": {
        "object": "list",
        "data": [
        ],
        "has_more": false,
        "url": "/v1/customers/cus_HSfjRanfIZeNYE/tax_ids"
      }
    },
    "previous_attributes": {
      "description": "Old description"
    }
  }
}"""
        % customer_id
    )


@pytest.mark.django_db
def test_stripe_webhook_handler_customer_updated(mocker: Any) -> None:
    """
    Verify our webhook handler updates our customer when we get a customer.updated event
    """
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    account = create_account()

    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    fake_customer = create_stripe_customer(id=account.stripe_customer_id, address=None)
    patched_retrieve_customer = mocker.patch(
        "web_api.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    patched_retrieve_subscription = mocker.patch(
        "web_api.views.stripe.Subscription.retrieve",
        return_value=create_stripe_subscription(),
    )
    patched_retrieve_payment_method = mocker.patch(
        "web_api.views.stripe.PaymentMethod.retrieve",
        return_value=create_stripe_payment_method(),
    )
    patched_update_bot = mocker.patch(
        "web_api.models.Account.update_bot", spec=Account.update_bot
    )
    assert StripeCustomerInformation.objects.count() == 1
    assert update_bot.call_count == 0
    assert patched_retrieve_customer.call_count == 0
    assert patched_retrieve_subscription.call_count == 0
    assert patched_retrieve_payment_method.call_count == 0
    res = post_webhook(make_customer_updated_event(account.stripe_customer_id))

    assert res.status_code == 200
    assert patched_update_bot.call_count == 1
    assert patched_retrieve_customer.call_count == 1
    assert patched_retrieve_subscription.call_count == 1
    assert patched_retrieve_payment_method.call_count == 1
    assert StripeCustomerInformation.objects.count() == 1
    updated_stripe_customer_info = StripeCustomerInformation.objects.get()
    assert updated_stripe_customer_info.customer_email == fake_customer.email
    assert updated_stripe_customer_info.customer_balance == fake_customer.balance
    assert updated_stripe_customer_info.customer_created == fake_customer.created
    assert updated_stripe_customer_info.customer_currency == fake_customer.currency
    assert updated_stripe_customer_info.customer_name == fake_customer.name

    assert fake_customer.address is None
    assert updated_stripe_customer_info.customer_address_line1 is None
    assert updated_stripe_customer_info.customer_address_city is None
    assert updated_stripe_customer_info.customer_address_country is None
    assert updated_stripe_customer_info.customer_address_line2 is None
    assert updated_stripe_customer_info.customer_address_postal_code is None
    assert updated_stripe_customer_info.customer_address_state is None


@pytest.mark.django_db
def test_stripe_webhook_handler_customer_updated_with_address(mocker: Any) -> None:
    """
    Verify our webhook handler updates our customer when we get a customer.updated event

    This is basically the same as the previous test but with the address provided.
    """
    update_bot = mocker.patch("web_api.models.Account.update_bot")
    account = create_account()

    create_stripe_customer_info(customer_id=account.stripe_customer_id)
    fake_customer = create_stripe_customer(id=account.stripe_customer_id,)
    patched_retrieve_customer = mocker.patch(
        "web_api.views.stripe.Customer.retrieve", return_value=fake_customer
    )
    patched_retrieve_subscription = mocker.patch(
        "web_api.views.stripe.Subscription.retrieve",
        return_value=create_stripe_subscription(),
    )
    patched_retrieve_payment_method = mocker.patch(
        "web_api.views.stripe.PaymentMethod.retrieve",
        return_value=create_stripe_payment_method(),
    )
    patched_update_bot = mocker.patch(
        "web_api.models.Account.update_bot", spec=Account.update_bot
    )
    assert StripeCustomerInformation.objects.count() == 1
    assert update_bot.call_count == 0
    assert patched_retrieve_customer.call_count == 0
    assert patched_retrieve_subscription.call_count == 0
    assert patched_retrieve_payment_method.call_count == 0
    res = post_webhook(make_customer_updated_event(account.stripe_customer_id))

    assert res.status_code == 200
    assert patched_update_bot.call_count == 1
    assert patched_retrieve_customer.call_count == 1
    assert patched_retrieve_subscription.call_count == 1
    assert patched_retrieve_payment_method.call_count == 1
    assert StripeCustomerInformation.objects.count() == 1
    updated_stripe_customer_info = StripeCustomerInformation.objects.get()
    assert updated_stripe_customer_info.customer_email == fake_customer.email
    assert updated_stripe_customer_info.customer_balance == fake_customer.balance
    assert updated_stripe_customer_info.customer_created == fake_customer.created
    assert updated_stripe_customer_info.customer_currency == fake_customer.currency
    assert updated_stripe_customer_info.customer_name == fake_customer.name

    assert fake_customer.address is not None
    assert (
        updated_stripe_customer_info.customer_address_line1
        == fake_customer.address.line1
    )
    assert (
        updated_stripe_customer_info.customer_address_city == fake_customer.address.city
    )
    assert (
        updated_stripe_customer_info.customer_address_country
        == fake_customer.address.country
    )
    assert (
        updated_stripe_customer_info.customer_address_line2
        == fake_customer.address.line2
    )
    assert (
        updated_stripe_customer_info.customer_address_postal_code
        == fake_customer.address.postal_code
    )
    assert (
        updated_stripe_customer_info.customer_address_state
        == fake_customer.address.state
    )


@pytest.mark.django_db
def test_stripe_webhook_handler_customer_updated_no_matching_customer(
    mocker: Any,
) -> None:
    """
    If we get a customer.updated event for a non existent customer we should error.
    """
    account = create_account()

    patched_update_from_stripe = mocker.patch(
        "web_api.models.StripeCustomerInformation.update_from_stripe",
        spec=StripeCustomerInformation.update_from_stripe,
    )
    mocker.patch("web_api.models.Account.update_bot", spec=Account.update_bot)
    assert StripeCustomerInformation.objects.count() == 0
    assert patched_update_from_stripe.call_count == 0
    res = post_webhook(make_customer_updated_event(account.stripe_customer_id))

    assert res.status_code == 400
    assert StripeCustomerInformation.objects.count() == 0
    assert patched_update_from_stripe.call_count == 0


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
def test_healthcheck(client: Client) -> None:
    """
    We should return 200 even when logged out.
    """
    res = client.get("/v1/healthcheck")
    assert res.status_code == 200
    assert res.json()["ok"] is True


@pytest.mark.django_db
def test_oauth_login(client: Client, state_token: str) -> None:
    res = client.get("/v1/oauth_login", dict(state=state_token))
    assert res.status_code == 302
    assert (
        res["Location"]
        == f"https://github.com/login/oauth/authorize?client_id=Iv1.111FAKECLIENTID111&redirect_uri=https://app.kodiakhq.com/oauth&state={state_token}"
    )


@pytest.fixture
def successful_sync_accounts_response(mocked_responses: responses.RequestsMock) -> None:
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
def successful_responses(mocked_responses: responses.RequestsMock) -> None:
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
def failing_sync_accounts_response(mocked_responses: responses.RequestsMock) -> None:
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
