from typing import Any

import pytest
import stripe

from web_api import billing
from web_api.models import Account, StripeCustomerInformation
from web_api.testutils import (
    create_account,
    create_stripe_customer,
    create_stripe_customer_info,
    create_stripe_invoice,
    create_stripe_product,
    create_stripe_subscription,
)


@pytest.mark.django_db
def test_update_customer(mocker: Any) -> None:
    """
    We should update the customer information if we have a corresponding
    subscription row.
    """
    account = create_account()
    billing.update_customer(customer_id=account.stripe_customer_id)
    assert StripeCustomerInformation.objects.count() == 0

    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    assert account.get_stripe_customer_info() == stripe_customer_info

    fake_stripe_customer = create_stripe_customer(
        email="j.doe@exa.com",
        name="Exa Corp",
        address=dict(
            line1="1 Main St",
            line2="Floor 42",
            city="Honolulu",
            state="HI",
            postal_code="96813",
            country="USA",
        ),
    )

    assert stripe_customer_info.customer_name != fake_stripe_customer.name
    assert stripe_customer_info.customer_email != fake_stripe_customer.email
    assert (
        stripe_customer_info.customer_address_line1
        != fake_stripe_customer.address.line1
    )
    assert (
        stripe_customer_info.customer_address_line2
        != fake_stripe_customer.address.line2
    )
    assert (
        stripe_customer_info.customer_address_city != fake_stripe_customer.address.city
    )
    assert (
        stripe_customer_info.customer_address_state
        != fake_stripe_customer.address.state
    )
    assert (
        stripe_customer_info.customer_address_postal_code
        != fake_stripe_customer.address.postal_code
    )
    assert (
        stripe_customer_info.customer_address_country
        != fake_stripe_customer.address.country
    )

    patched_stripe_customer_retrieve = mocker.patch(
        "web_api.billing.stripe.Customer.retrieve",
        spec=stripe.Customer.retrieve,
        return_value=fake_stripe_customer,
    )
    billing.update_customer(customer_id=account.stripe_customer_id)

    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.customer_name == fake_stripe_customer.name
    assert stripe_customer_info.customer_email == fake_stripe_customer.email
    assert (
        stripe_customer_info.customer_address_line1
        == fake_stripe_customer.address.line1
    )
    assert (
        stripe_customer_info.customer_address_line2
        == fake_stripe_customer.address.line2
    )
    assert (
        stripe_customer_info.customer_address_city == fake_stripe_customer.address.city
    )
    assert (
        stripe_customer_info.customer_address_state
        == fake_stripe_customer.address.state
    )
    assert (
        stripe_customer_info.customer_address_postal_code
        == fake_stripe_customer.address.postal_code
    )
    assert (
        stripe_customer_info.customer_address_country
        == fake_stripe_customer.address.country
    )
    assert patched_stripe_customer_retrieve.call_count == 1


@pytest.mark.django_db
def test_handle_subscription_update(mocker: Any) -> None:
    account = create_account()
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    patched_customer_retrieve = mocker.patch(
        "web_api.billing.stripe.Customer.retrieve",
        spec=stripe.Customer.retrieve,
        return_value=create_stripe_customer(id=account.stripe_customer_id),
    )
    patched_subscription_retrieve = mocker.patch(
        "web_api.billing.stripe.Subscription.retrieve",
        spec=stripe.Subscription.retrieve,
        return_value=create_stripe_subscription(
            cancel_at=1703059813, canceled_at=1653059813
        ),
    )
    patched_product_retrieve = mocker.patch(
        "web_api.billing.stripe.Product.retrieve",
        spec=stripe.Product.retrieve,
        return_value=create_stripe_product(),
    )
    patched_invoice_upcoming = mocker.patch(
        "web_api.billing.stripe.Invoice.upcoming",
        spec=stripe.Invoice.upcoming,
        return_value=create_stripe_invoice(),
    )
    patched_account_update_bot = mocker.patch(
        "web_api.billing.Account.update_bot", spec=Account.update_bot,
    )
    assert StripeCustomerInformation.objects.count() == 1
    billing.handle_subscription_update(customer_id=account.stripe_customer_id)
    assert StripeCustomerInformation.objects.count() == 1
    stripe_customer_info.refresh_from_db()
    assert stripe_customer_info.subscription_cancel_at == 1703059813
    assert stripe_customer_info.subscription_canceled_at == 1653059813
    assert patched_invoice_upcoming.call_count == 0
    for patch in (
        patched_customer_retrieve,
        patched_subscription_retrieve,
        patched_product_retrieve,
        patched_account_update_bot,
    ):
        assert patch.call_count == 1


@pytest.mark.django_db
def test_handle_checkout_complete(mocker: Any) -> None:
    """
    Create a subscription and sync customer.
    """
    customer_id = "cus_i8Pfx3h"
    account = create_account(stripe_customer_id="")
    patched_customer_retrieve = mocker.patch(
        "web_api.billing.stripe.Customer.retrieve",
        spec=stripe.Customer.retrieve,
        return_value=create_stripe_customer(id=customer_id),
    )
    patched_subscription_retrieve = mocker.patch(
        "web_api.billing.stripe.Subscription.retrieve",
        spec=stripe.Subscription.retrieve,
        return_value=create_stripe_subscription(),
    )
    patched_product_retrieve = mocker.patch(
        "web_api.billing.stripe.Product.retrieve",
        spec=stripe.Product.retrieve,
        return_value=create_stripe_product(),
    )
    patched_invoice_upcoming = mocker.patch(
        "web_api.billing.stripe.Invoice.upcoming",
        spec=stripe.Invoice.upcoming,
        return_value=create_stripe_invoice(),
    )
    patched_account_update_bot = mocker.patch(
        "web_api.billing.Account.update_bot", spec=Account.update_bot,
    )
    assert account.stripe_customer_id == ""
    assert StripeCustomerInformation.objects.count() == 0

    billing.handle_checkout_complete(
        account_id=str(account.id), customer_id=customer_id
    )

    account.refresh_from_db()
    assert account.stripe_customer_id == customer_id
    stripe_customer_info = account.get_stripe_customer_info()
    assert stripe_customer_info is not None
    assert StripeCustomerInformation.objects.count() == 1
    for patch in (
        patched_customer_retrieve,
        patched_subscription_retrieve,
        patched_product_retrieve,
        patched_invoice_upcoming,
        patched_account_update_bot,
    ):
        assert patch.call_count == 1

    for field in (
        "customer_address_city",
        "customer_address_country",
        "customer_address_line2",
        "customer_address_postal_code",
        "customer_address_state",
        "subscription_id",
        "subscription_quantity",
        "subscription_start_date",
        "subscription_current_period_end",
        "subscription_current_period_start",
        "plan_id",
        "plan_amount",
        "plan_interval",
        "plan_interval_count",
        "plan_product_name",
        "upcoming_invoice_total",
    ):
        assert getattr(stripe_customer_info, field) is not None

    for field in (
        "subscription_cancel_at",
        "subscription_canceled_at",
    ):
        assert getattr(stripe_customer_info, field) is None


@pytest.mark.django_db
def test_handle_checkout_complete_existing_subscription(mocker: Any) -> None:
    """
    Create a subscription and sync customer.
    """
    customer_id = "cus_i8Pfx3h"
    account = create_account(stripe_customer_id="")
    patched_customer_retrieve = mocker.patch(
        "web_api.billing.stripe.Customer.retrieve",
        spec=stripe.Customer.retrieve,
        return_value=create_stripe_customer(id=customer_id),
    )
    patched_subscription_retrieve = mocker.patch(
        "web_api.billing.stripe.Subscription.retrieve",
        spec=stripe.Subscription.retrieve,
        return_value=create_stripe_subscription(),
    )
    patched_product_retrieve = mocker.patch(
        "web_api.billing.stripe.Product.retrieve",
        spec=stripe.Product.retrieve,
        return_value=create_stripe_product(),
    )
    patched_invoice_upcoming = mocker.patch(
        "web_api.billing.stripe.Invoice.upcoming",
        spec=stripe.Invoice.upcoming,
        return_value=create_stripe_invoice(),
    )
    patched_account_update_bot = mocker.patch(
        "web_api.billing.Account.update_bot", spec=Account.update_bot,
    )
    assert account.stripe_customer_id == ""
    assert StripeCustomerInformation.objects.count() == 0

    billing.handle_checkout_complete(
        account_id=str(account.id), customer_id=customer_id
    )

    account.refresh_from_db()
    assert account.stripe_customer_id == customer_id
    stripe_customer_info = account.get_stripe_customer_info()
    assert stripe_customer_info is not None
    assert StripeCustomerInformation.objects.count() == 1
    for patch in (
        patched_customer_retrieve,
        patched_subscription_retrieve,
        patched_product_retrieve,
        patched_invoice_upcoming,
        patched_account_update_bot,
    ):
        assert patch.call_count == 1


@pytest.mark.django_db
def test_cancel_subscription(mocker: Any) -> None:
    """
    We should delete the subscription object and update the subscription status
    in Redis for the bot via `.update_bot`
    """
    account = create_account()
    stripe_customer_info = create_stripe_customer_info(
        customer_id=account.stripe_customer_id
    )
    assert account.get_stripe_customer_info() == stripe_customer_info
    patched_update_bot = mocker.patch(
        "web_api.billing.Account.update_bot", spec=Account.update_bot
    )

    billing.cancel_subscription(stripe_customer_info.customer_id)
    assert account.get_stripe_customer_info() is None
    assert StripeCustomerInformation.objects.count() == 0
    assert patched_update_bot.call_count == 1
