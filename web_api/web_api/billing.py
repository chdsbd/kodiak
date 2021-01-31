import logging

import stripe

from web_api.models import Account, StripeCustomerInformation

logger = logging.getLogger(__name__)


def update_customer(customer_id: str) -> None:
    """
    Update customer billing info from Stripe
    """
    account = Account.objects.filter(stripe_customer_id=customer_id).get()
    stripe_customer_info = account.get_stripe_customer_info()
    if stripe_customer_info:
        customer = stripe.Customer.retrieve(customer_id)
        stripe_customer_info.update_from(customer)


def update_subscription(
    account: Account,
    customer: stripe.Customer,
    stripe_customer_info: StripeCustomerInformation,
) -> None:
    sub_count = len(customer.subscriptions.data)
    if sub_count > 1:
        logger.warning(
            "Found %s subscriptions for customer. Expected 0 or 1.", sub_count
        )

    subscription = stripe.Subscription.retrieve(customer.subscriptions.data[0].id)
    product = stripe.Product.retrieve(subscription.plan.product)

    if not subscription.canceled_at:
        upcoming_invoice = stripe.Invoice.upcoming(subscription=subscription.id)
    else:
        upcoming_invoice = None
    stripe_customer_info.update_from(
        customer=customer,
        subscription=subscription,
        product=product,
        upcoming_invoice=upcoming_invoice,
    )
    account.update_bot()


def handle_subscription_update(customer_id: str) -> None:
    """
    Sync subscription info from Stripe
    """
    customer = stripe.Customer.retrieve(customer_id)
    account = Account.objects.get(stripe_customer_id=customer.id)

    stripe_customer_info = account.get_stripe_customer_info()
    assert stripe_customer_info is not None

    update_subscription(
        account=account, customer=customer, stripe_customer_info=stripe_customer_info
    )


def handle_checkout_complete(account_id: str, customer_id: str) -> None:
    """
    Create and sync subscription info from Stripe
    """
    account = Account.objects.get(id=account_id)
    customer = stripe.Customer.retrieve(customer_id)
    account.stripe_customer_id = customer.id
    account.save()

    try:
        stripe_customer_info = StripeCustomerInformation.objects.get(
            customer_id=account.stripe_customer_id
        )
    except StripeCustomerInformation.DoesNotExist:
        stripe_customer_info = StripeCustomerInformation(
            customer_id=account.stripe_customer_id
        )
    update_subscription(
        account=account, customer=customer, stripe_customer_info=stripe_customer_info
    )


def cancel_subscription(customer_id: str) -> None:
    """
    Remove cancelled subscription
    """
    StripeCustomerInformation.objects.filter(customer_id=customer_id).delete()
    account = Account.objects.get(stripe_customer_id=customer_id)
    # update subscription info in Redis
    account.update_bot()
