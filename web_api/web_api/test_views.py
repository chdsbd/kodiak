import datetime
import json
import time
from typing import Any, Optional, Tuple, Type, Union, cast

import pytest
import responses
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from typing_extensions import Literal

import web_api.billing
from web_api.models import (
    Account,
    AccountMembership,
    AccountType,
    PullRequestActivity,
    User,
    UserPullRequestActivity,
)
from web_api.testutils import TestClient as Client
from web_api.testutils import (
    create_account,
    create_org_account,
    create_stripe_customer,
    create_stripe_customer_info,
    create_stripe_subscription,
)


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
    user_account = create_account(github_account_login=user.github_login,)
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
            firstActiveDate="2020-12-05",
            lastActiveDate="2020-12-05",
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
    assert res.json()["subscription"]["cost"]["planInterval"] == "month"
    assert res.json()["subscription"]["billingEmail"] == "accounting@acme-corp.com"
    assert res.json()["subscription"]["contactEmails"] == ""
    assert res.json()["subscription"]["customerName"] is None
    assert res.json()["subscription"]["customerAddress"] is None

    stripe_customer_information.plan_interval = "year"
    stripe_customer_information.save()
    res = authed_client.get(f"/v1/t/{account.id}/usage_billing")
    assert res.status_code == 200
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


@pytest.fixture
def patch_cancel_subscription(mocker: Any) -> None:
    mocker.patch("web_api.models.stripe.Subscription.delete")
    mocker.patch("web_api.models.Account.update_bot")


@pytest.mark.django_db
def test_activity(authed_client: Client, user: User,) -> None:
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


@pytest.mark.django_db
def test_activity_authentication(authed_client: Client, other_user: User,) -> None:
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
def test_update_stripe_customer_info_permission(
    authed_client: Client, user: User
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
    authed_client: Client, user: User, mocker: Any
) -> None:
    fake_customer = create_stripe_customer(email="billing@kodiakhq.com")
    patch_stripe_customer_modify = mocker.patch(
        "web_api.models.stripe.Customer.modify",
        spec=stripe.Customer.modify,
        return_value=fake_customer,
    )
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
    assert patch_stripe_customer_modify.call_count == 1


@pytest.mark.django_db
def test_update_billing_email(authed_client: Client, user: User, mocker: Any) -> None:
    """
    A user should be able to modifying billing email.
    """
    fake_customer = create_stripe_customer(email="billing@kodiakhq.com")
    patch_stripe_customer_modify = mocker.patch(
        "web_api.models.stripe.Customer.modify",
        spec=stripe.Customer.modify,
        return_value=fake_customer,
    )
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
    assert patch_stripe_customer_modify.call_count == 1


@pytest.mark.django_db
def test_update_billing_email_empty(
    authed_client: Client, user: User, mocker: Any
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
def test_update_contact_emails(authed_client: Client, user: User, mocker: Any) -> None:
    """
    User should be able to set contact emails
    """
    account, membership = create_org_account(user)

    original_email = "j.doe@acme-inc.corp"
    account.original_email = original_email
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
def test_update_company_name(authed_client: Client, user: User, mocker: Any) -> None:
    """
    A user should be able to modify the company name.
    """
    patch_stripe_customer_modify = mocker.patch(
        "web_api.models.stripe.Customer.modify",
        spec=stripe.Customer.modify,
        return_value=create_stripe_customer(name="Kodiak Bait & Tackle"),
    )
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
    assert patch_stripe_customer_modify.call_count == 1


@pytest.mark.django_db
def test_update_address(authed_client: Client, user: User, mocker: Any) -> None:
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
    patch_stripe_customer_modify = mocker.patch(
        "web_api.models.stripe.Customer.modify",
        spec=stripe.Customer.modify,
        return_value=create_stripe_customer(
            address=dict(
                line1="123 Main St",
                line2="Apt 3B",
                city="Anytown",
                postal_code="12345",
                state="Massachusetts",
                country="United States",
            )
        ),
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
    assert patch_stripe_customer_modify.call_count == 1


@pytest.mark.django_db
def test_update_limit_billing_access_to_owners(
    authed_client: Client, user: User, mocker: Any
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
    user_account = create_account(github_account_login=other_user.github_login,)
    AccountMembership.objects.create(
        account=user_account, user=other_user, role="member"
    )
    res = authed_client.get(f"/v1/t/{user_account.id}/current_account")
    assert res.status_code == 404


@pytest.mark.django_db
def test_accounts(authed_client: Client, user: User) -> None:
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
    accounts = sorted(res.json(), key=lambda x: x["name"])
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
def test_stripe_webhook_handler_checkout_session_complete_subscription(
    mocker: Any,
) -> None:
    """
    Verify our webhook handler triggers checkout code
    """
    customer_id = "cus_Gz7jQFKdh4KirU"
    patched_handle_checkout_complete = mocker.patch(
        "web_api.views.billing.handle_checkout_complete",
        spec=web_api.billing.handle_checkout_complete,
    )
    assert patched_handle_checkout_complete.call_count == 0
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
        % customer_id
    )
    assert res.status_code == 200
    assert patched_handle_checkout_complete.call_count == 1


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
    Verify our webhook handler triggers call to update our customer
    """
    patched_update_customer = mocker.patch(
        "web_api.views.billing.update_customer", spec=web_api.billing.update_customer,
    )
    res = post_webhook(make_customer_updated_event("cus_Gxfda4f23"))
    assert res.status_code == 200
    assert patched_update_customer.call_count == 1


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
