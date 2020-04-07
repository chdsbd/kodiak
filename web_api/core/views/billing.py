import logging
import time
from typing import Optional

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from core import auth
from core.exceptions import BadRequest, PermissionDenied, UnprocessableEntity
from core.models import Account, StripeCustomerInformation, UserPullRequestActivity

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@auth.login_required
def usage_billing(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    active_users = UserPullRequestActivity.get_active_users_in_last_30_days(account)
    subscription = None
    trial = None
    if account.trial_start and account.trial_expiration and account.trial_started_by:
        trial = dict(
            startDate=account.trial_start,
            endDate=account.trial_expiration,
            expired=account.trial_expired(),
            startedBy=dict(
                id=account.trial_started_by.id,
                name=account.trial_started_by.github_login,
                profileImgUrl=account.trial_started_by.profile_image(),
            ),
        )
    stripe_customer_info = account.stripe_customer_info()
    if stripe_customer_info:
        subscription = dict(
            seats=stripe_customer_info.subscription_quantity,
            nextBillingDate=stripe_customer_info.next_billing_date,
            expired=stripe_customer_info.expired,
            cost=dict(
                totalCents=stripe_customer_info.plan_amount
                * stripe_customer_info.subscription_quantity,
                perSeatCents=stripe_customer_info.plan_amount,
            ),
            billingEmail=stripe_customer_info.customer_email,
            cardInfo=f"{stripe_customer_info.payment_method_card_brand.title()} ({stripe_customer_info.payment_method_card_last4})",
        )
    return JsonResponse(
        dict(
            subscription=subscription,
            trial=trial,
            activeUsers=[
                dict(
                    id=active_user.github_id,
                    name=active_user.github_login,
                    profileImgUrl=active_user.profile_image(),
                    interactions=active_user.days_active,
                    lastActiveDate=active_user.last_active_at.isoformat(),
                )
                for active_user in active_users
            ],
        )
    )


@auth.login_required
def start_trial(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    billing_email = request.POST["billingEmail"]
    account.start_trial(request.user, billing_email=billing_email)
    return HttpResponse(status=204)


@auth.login_required
def update_subscription(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    # restrict updates to admins
    if not request.user.can_edit(account):
        raise PermissionDenied
    seats = int(request.POST["seats"])
    proration_timestamp = int(request.POST["prorationTimestamp"])
    stripe_customer_info = account.stripe_customer_info()
    if stripe_customer_info is None:
        raise UnprocessableEntity("Subscription does not exist to modify.")

    subscription = stripe.Subscription.retrieve(stripe_customer_info.subscription_id)
    updated_subscription = stripe.Subscription.modify(
        subscription.id,
        items=[
            {
                "id": subscription["items"]["data"][0].id,
                "plan": stripe_customer_info.plan_id,
                "quantity": seats,
            }
        ],
        proration_date=proration_timestamp,
    )
    # when we upgrade a users plan Stripe will charge them on their next billing
    # cycle. To make Stripe charge for the upgrade immediately we must create an
    # invoice and pay it. If we don't pay the invoice Stripe will wait 1 hour
    # before attempting to charge user.
    invoice = stripe.Invoice.create(
        customer=stripe_customer_info.customer_id, auto_advance=True
    )
    # we must specify the payment method because our Stripe customers don't have
    # a default payment method, so the default invoicing will fail.
    stripe.Invoice.pay(invoice.id, payment_method=subscription.default_payment_method)
    stripe_customer_info.plan_amount = updated_subscription.plan.amount

    stripe_customer_info.subscription_quantity = updated_subscription.quantity
    stripe_customer_info.subscription_current_period_end = (
        updated_subscription.current_period_end
    )
    stripe_customer_info.subscription_current_period_start = (
        updated_subscription.current_period_start
    )
    stripe_customer_info.save()

    return HttpResponse(status=204)


@auth.login_required
def start_checkout(request: HttpRequest, team_id: str) -> HttpResponse:
    seat_count = int(request.POST.get("seatCount", 1))
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    # if available, using the existing customer_id allows us to pre-fill the
    # checkout form with their email.
    customer_id = account.stripe_customer_id or None

    # https://stripe.com/docs/api/checkout/sessions/create
    session = stripe.checkout.Session.create(
        client_reference_id=account.id,
        customer=customer_id,
        # cards only work with subscriptions and StripeCustomerInformation
        # depends on credit cards
        # (payment_method_card_{brand,exp_month,exp_year,last4}).
        payment_method_types=["card"],
        subscription_data={
            "items": [{"plan": settings.STRIPE_PLAN_ID, "quantity": seat_count}],
        },
        success_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?install_complete=1",
        cancel_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?start_subscription=1",
    )
    return JsonResponse(
        dict(
            stripeCheckoutSessionId=session.id,
            stripePublishableApiKey=settings.STRIPE_PUBLISHABLE_API_KEY,
        )
    )


@auth.login_required
def modify_payment_details(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    session = stripe.checkout.Session.create(
        client_reference_id=account.id,
        customer=account.stripe_customer_id or None,
        mode="setup",
        payment_method_types=["card"],
        success_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?install_complete=1",
        cancel_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?modify_subscription=1",
    )
    return JsonResponse(
        dict(
            stripeCheckoutSessionId=session.id,
            stripePublishableApiKey=settings.STRIPE_PUBLISHABLE_API_KEY,
        )
    )


@auth.login_required
def cancel_subscription(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    if not request.user.can_edit(account):
        raise PermissionDenied

    customer_info = account.stripe_customer_info()
    if customer_info is not None:
        customer_info.cancel_subscription()
    return HttpResponse(status=204)


@auth.login_required
def fetch_proration(request: HttpRequest, team_id: str) -> HttpResponse:
    account = get_object_or_404(
        Account.objects.filter(memberships__user=request.user), id=team_id
    )
    subscription_quantity = int(request.POST["subscriptionQuantity"])

    customer_info = account.stripe_customer_info()
    if customer_info is not None:
        proration_date = int(time.time())
        return JsonResponse(
            dict(
                proratedCost=customer_info.preview_proration(
                    timestamp=proration_date,
                    subscription_quantity=subscription_quantity,
                ),
                prorationTime=proration_date,
            )
        )
    return HttpResponse(status=500)


def stripe_webhook_handler(request: HttpRequest) -> HttpResponse:
    """
    After checkout, Stripe sends a checkout.session.completed event. Stripe will
    wait up to 10 seconds for this webhook to return before redirecting a user
    back to the return URL.

    https://stripe.com/docs/billing/webhooks
    """
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    try:
        event = stripe.Webhook.construct_event(
            payload=request.body,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        # Invalid payload
        logger.warning("problem parsing stripe payload", exc_info=True)
        raise BadRequest
    except stripe.error.SignatureVerificationError:
        logger.warning("invalid signature for webhook request", exc_info=True)
        raise BadRequest

    # https://stripe.com/docs/billing/lifecycle#subscription-lifecycle

    # triggered when a customer completes the Stripe Checkout form.
    # https://stripe.com/docs/payments/checkout/fulfillment#webhooks
    if event.type == "checkout.session.completed":
        # Stripe will wait until this webhook handler returns to redirect from checkout
        checkout_session = event.data.object
        if checkout_session.mode == "setup":
            # a setup checkout session occurs when a user updates their payment
            # method or billing email. We update the associated account and
            # stripe_customer_info on this event. Setup should occur after a
            # subscription has been created.
            account = Account.objects.get(id=checkout_session.client_reference_id)
            customer = stripe.Customer.retrieve(checkout_session.customer)
            account.update_from(customer)
            stripe_customer_info = account.stripe_customer_info()
            if stripe_customer_info is None:
                logger.warning("expected account %s to have customer info", account)
                return HttpResponse(status=200)
            subscription = stripe.Subscription.retrieve(
                stripe_customer_info.subscription_id
            )
            payment_method = stripe.PaymentMethod.retrieve(
                subscription.default_payment_method
            )
            stripe_customer_info.update_from(
                customer=customer,
                subscription=subscription,
                payment_method=payment_method,
            )
        elif checkout_session.mode == "subscription":
            # subscription occurs after a user creates a subscription through
            # the checkout.
            account = Account.objects.get(id=checkout_session.client_reference_id)
            subscription = stripe.Subscription.retrieve(checkout_session.subscription)
            customer = stripe.Customer.retrieve(checkout_session.customer)
            payment_method = stripe.PaymentMethod.retrieve(
                subscription.default_payment_method
            )

            account.update_from(customer=customer)

            try:
                stripe_customer_info = StripeCustomerInformation.objects.get(
                    customer_id=customer.id
                )
            except StripeCustomerInformation.DoesNotExist:
                stripe_customer_info = StripeCustomerInformation(
                    customer_id=customer.id
                )
            stripe_customer_info.update_from(
                subscription=subscription,
                customer=customer,
                payment_method=payment_method,
            )
        else:
            raise BadRequest
        # Then define and call a method to handle the successful payment intent.
        # handle_payment_intent_succeeded(payment_intent)
    elif event.type == "invoice.payment_succeeded":
        # triggered whenever a subscription is paid. We need to update the
        # subscription to have the correct period information.
        invoice = event.data.object
        if not invoice.paid:
            logger.warning("invoice not paid %s", event)
            return HttpResponse(status=200)
        stripe_customer: Optional[
            StripeCustomerInformation
        ] = StripeCustomerInformation.objects.filter(
            customer_id=invoice.customer
        ).first()
        if stripe_customer is None:
            logger.warning(
                "expected invoice to have corresponding StripeCustomerInformation"
            )
            raise BadRequest
        stripe_customer.subscription_current_period_end = invoice.period_end
        stripe_customer.subscription_current_period_start = invoice.period_start
        stripe_customer.save()
    elif event.type == "customer.subscription.deleted":
        # I don't think we need to do anything on subscription deletion. We can
        # let the subscription time run out.
        pass
    elif event.type == "invoice.payment_action_required":
        logger.warning("more action required for payment %s", event)
    elif event.type == "invoice.payment_failed":
        logger.warning("invoice.payment_failed %s", event)
    else:
        # Unexpected event type
        raise BadRequest

    return HttpResponse(status=200)
