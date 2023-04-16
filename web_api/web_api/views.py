import logging
import time
from dataclasses import asdict, dataclass
from typing import Optional, Union, cast
from urllib.parse import parse_qsl

import pydantic
import requests
import sentry_sdk
import stripe
from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from typing_extensions import Literal
from yarl import URL

from web_api import auth
from web_api.auth import AuthedHttpRequest
from web_api.exceptions import BadRequest, PermissionDenied, UnprocessableEntity
from web_api.http import JsonResponse
from web_api.merge_queues import get_active_merge_queues
from web_api.models import (
    Account,
    Address,
    AnonymousUser,
    PullRequestActivity,
    StripeCustomerInformation,
    SyncAccountsError,
    User,
    UserPullRequestActivity,
)

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def get_account_or_404(*, team_id: str, user: User) -> Account:
    return get_object_or_404(Account.objects.filter(memberships__user=user), id=team_id)


@auth.login_required
def ping(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": True})


def healthcheck(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": True})


DEFAULT_CURRENCY = "usd"


@auth.login_required
def usage_billing(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(user=request.user, team_id=team_id)
    active_users = UserPullRequestActivity.get_active_users_in_last_30_days(account)
    subscription = None
    trial = None
    if account.trial_start and account.trial_expiration and account.trial_started_by:
        trial = {
            "startDate": account.trial_start,
            "endDate": account.trial_expiration,
            "expired": account.trial_expired(),
            "startedBy": {
                "id": account.trial_started_by.id,
                "name": account.trial_started_by.github_login,
                "profileImgUrl": account.trial_started_by.profile_image(),
            },
        }
    stripe_customer_info = account.stripe_customer_info()
    if stripe_customer_info:
        customer_address = None
        if stripe_customer_info.customer_address_line1 is not None:
            customer_address = {
                "line1": stripe_customer_info.customer_address_line1,
                "city": stripe_customer_info.customer_address_city,
                "country": stripe_customer_info.customer_address_country,
                "line2": stripe_customer_info.customer_address_line2,
                "postalCode": stripe_customer_info.customer_address_postal_code,
                "state": stripe_customer_info.customer_address_state,
            }
        plan_interval = (
            "year" if stripe_customer_info.plan_interval == "year" else "month"
        )
        brand_title = (
            stripe_customer_info.payment_method_card_brand.title()
            if stripe_customer_info.payment_method_card_brand is not None
            else None
        )
        subscription = {
            "seats": stripe_customer_info.subscription_quantity,
            "nextBillingDate": stripe_customer_info.next_billing_date,
            "expired": stripe_customer_info.expired,
            "cost": {
                "totalCents": stripe_customer_info.plan_amount
                * stripe_customer_info.subscription_quantity,
                "perSeatCents": stripe_customer_info.plan_amount,
                "currency": stripe_customer_info.customer_currency or DEFAULT_CURRENCY,
                "planInterval": plan_interval,
            },
            "billingEmail": stripe_customer_info.customer_email,
            "contactEmails": account.contact_emails,
            "customerName": stripe_customer_info.customer_name,
            "customerAddress": customer_address,
            "cardInfo": f"{brand_title} ({stripe_customer_info.payment_method_card_last4})",
            "viewerIsOrgOwner": request.user.is_admin(account),
            "viewerCanModify": request.user.can_edit_subscription(account),
            "limitBillingAccessToOwners": account.limit_billing_access_to_owners,
        }

    subscription_quantity = (
        stripe_customer_info.subscription_quantity if stripe_customer_info else 0
    )
    # we assign seats to users in order of first active for the last 30 days.
    allowed_user_ids = {
        user.github_id
        for user in sorted(active_users, key=lambda x: x.first_active_at)[
            :subscription_quantity
        ]
    }
    active_user_with_license_info = [
        {
            "id": active_user.github_id,
            "name": active_user.github_login,
            "profileImgUrl": active_user.profile_image(),
            "interactions": active_user.days_active,
            "lastActiveDate": active_user.last_active_at.isoformat(),
            "firstActiveDate": active_user.first_active_at.isoformat(),
            "hasSeatLicense": (active_user.github_id in allowed_user_ids),
        }
        for active_user in active_users
    ]
    subscription_exemption = None

    if account.subscription_exempt:
        subscription_exemption = {"message": account.subscription_exempt_message}

    return JsonResponse(
        {
            "accountCanSubscribe": account.can_subscribe(),
            "subscription": subscription,
            "trial": trial,
            "activeUsers": active_user_with_license_info,
            "subscriptionExemption": subscription_exemption,
        }
    )


@auth.login_required
def activity(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)
    kodiak_activity_labels = []
    kodiak_activity_approved = []
    kodiak_activity_merged = []
    kodiak_activity_updated = []

    total_labels = []
    total_opened = []
    total_merged = []
    total_closed = []
    for day_activity in PullRequestActivity.objects.filter(
        github_installation_id=account.github_installation_id
    ).order_by("date"):
        kodiak_activity_labels.append(day_activity.date)
        kodiak_activity_approved.append(day_activity.kodiak_approved)
        kodiak_activity_merged.append(day_activity.kodiak_merged)
        kodiak_activity_updated.append(day_activity.kodiak_updated)
        total_labels.append(day_activity.date)
        total_opened.append(day_activity.total_opened)
        total_merged.append(day_activity.total_merged)
        total_closed.append(day_activity.total_closed)

    active_merge_queues = [
        {"owner": repo.owner, "repo": repo.repo, "queues": queues}
        for repo, queues in get_active_merge_queues(
            install_id=str(account.github_installation_id)
        ).items()
    ]

    return JsonResponse(
        {
            "kodiakActivity": {
                "labels": kodiak_activity_labels,
                "datasets": {
                    "approved": kodiak_activity_approved,
                    "merged": kodiak_activity_merged,
                    "updated": kodiak_activity_updated,
                },
            },
            "pullRequestActivity": {
                "labels": total_labels,
                "datasets": {
                    "opened": total_opened,
                    "merged": total_merged,
                    "closed": total_closed,
                },
            },
            "activeMergeQueues": active_merge_queues,
        }
    )


@auth.login_required
def current_account(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)
    return JsonResponse(
        {
            "user": {
                "id": request.user.id,
                "name": request.user.github_login,
                "profileImgUrl": request.user.profile_image(),
            },
            "org": {
                "id": account.id,
                "name": account.github_account_login,
                "profileImgUrl": account.profile_image(),
            },
            "accounts": [
                {
                    "id": x.id,
                    "name": x.github_account_login,
                    "profileImgUrl": x.profile_image(),
                }
                for x in Account.objects.filter(memberships__user=request.user)
            ],
        }
    )


@auth.login_required
def start_trial(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)
    billing_email = request.POST["billingEmail"]
    account.start_trial(request.user, billing_email=billing_email)
    return HttpResponse(status=204)


class UpdateSubscriptionModel(pydantic.BaseModel):
    seats: int
    prorationTimestamp: int
    planPeriod: Literal["month", "year"] = "month"


@auth.login_required
def update_subscription(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    payload = UpdateSubscriptionModel.parse_obj(request.POST.dict())
    account = get_account_or_404(team_id=team_id, user=request.user)
    if not request.user.can_edit_subscription(account):
        raise PermissionDenied
    stripe_customer_info = account.stripe_customer_info()
    if stripe_customer_info is None:
        raise UnprocessableEntity("Subscription does not exist to modify.")

    subscription = stripe.Subscription.retrieve(stripe_customer_info.subscription_id)
    updated_subscription = stripe.Subscription.modify(
        subscription.id,
        items=[
            {
                "id": subscription["items"]["data"][0].id,
                "plan": plan_id_from_period(period=payload.planPeriod),
                "quantity": payload.seats,
            }
        ],
        proration_date=payload.prorationTimestamp,
    )
    # we only need to manually created invoices when a user modifies their
    # subscription within the same billing period.
    if payload.planPeriod == subscription.plan.interval:
        # when we upgrade a users plan Stripe will charge them on their next billing
        # cycle. To make Stripe charge for the upgrade immediately we must create an
        # invoice and pay it. If we don't pay the invoice Stripe will wait 1 hour
        # before attempting to charge user.
        invoice = stripe.Invoice.create(
            customer=stripe_customer_info.customer_id, auto_advance=True
        )
        # we must specify the payment method because our Stripe customers don't have
        # a default payment method, so the default invoicing will fail.
        payment_methods = stripe.PaymentMethod.list(
            customer=subscription.customer,
            type="card",
        )

        payment_method = payment_methods.data[0].id

        stripe.Invoice.pay(invoice.id, payment_method=payment_method)
    stripe_customer_info.plan_amount = updated_subscription.plan.amount
    stripe_customer_info.plan_interval = updated_subscription.plan.interval

    stripe_customer_info.subscription_quantity = updated_subscription.quantity
    stripe_customer_info.subscription_current_period_end = (
        updated_subscription.current_period_end
    )
    stripe_customer_info.subscription_current_period_start = (
        updated_subscription.current_period_start
    )
    stripe_customer_info.save()
    account.update_bot()

    return HttpResponse(status=204)


class AddressModel(pydantic.BaseModel):
    line1: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    line2: Optional[str] = None
    postalCode: Optional[str] = None
    state: Optional[str] = None


class UpdateBillingInfoModel(pydantic.BaseModel):
    email: Optional[pydantic.EmailStr] = None
    name: Optional[str] = None
    address: Optional[AddressModel] = None
    contactEmails: Optional[str] = None
    limitBillingAccessToOwners: Optional[bool] = None


@auth.login_required
def update_stripe_customer_info(
    request: AuthedHttpRequest, team_id: str
) -> HttpResponse:
    """
    Endpoint to allow users to update Stripe customer info.
    """
    account = get_account_or_404(team_id=team_id, user=request.user)
    payload = UpdateBillingInfoModel.parse_raw(request.body)
    if payload.limitBillingAccessToOwners is not None:
        if not request.user.is_admin(account):
            raise PermissionDenied
        account.limit_billing_access_to_owners = payload.limitBillingAccessToOwners
        account.save()

    if payload.contactEmails is not None:
        if not request.user.can_edit_subscription(account):
            raise PermissionDenied
        account.contact_emails = payload.contactEmails
        account.save()

    if (
        payload.email is not None
        or payload.name is not None
        or payload.address is not None
    ):
        if not request.user.can_edit_subscription(account):
            raise PermissionDenied
        account.update_billing_info(
            email=payload.email,
            name=payload.name,
            address=(
                Address(
                    line1=payload.address.line1,
                    city=payload.address.city,
                    country=payload.address.country,
                    line2=payload.address.line2,
                    postal_code=payload.address.postalCode,
                    state=payload.address.state,
                )
                if payload.address is not None
                else None
            ),
        )
    return HttpResponse(status=204)


class StartCheckoutModal(pydantic.BaseModel):
    seatCount: int = 1
    planPeriod: Literal["month", "year"] = "month"


@auth.login_required
def start_checkout(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    payload = StartCheckoutModal.parse_obj(request.POST.dict())
    account = get_account_or_404(team_id=team_id, user=request.user)
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
            "items": [
                {
                    "plan": plan_id_from_period(period=payload.planPeriod),
                    "quantity": payload.seatCount,
                }
            ],
        },
        success_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?install_complete=1",
        cancel_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?start_subscription=1",
    )
    return JsonResponse(
        {
            "stripeCheckoutSessionId": session.id,
            "stripePublishableApiKey": settings.STRIPE_PUBLISHABLE_API_KEY,
        }
    )


@auth.login_required
def redirect_to_stripe_self_serve_portal(
    request: AuthedHttpRequest, team_id: str
) -> HttpResponse:
    """
    Redirect the user to the temp URL so they can access the stripe self serve portal

    https://stripe.com/docs/billing/subscriptions/integrating-self-serve-portal
    """
    account = get_account_or_404(team_id=team_id, user=request.user)

    customer_id = account.stripe_customer_id

    session_url = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage",
    ).url

    return HttpResponseRedirect(session_url)


@auth.login_required
def modify_payment_details(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)
    if not request.user.can_edit_subscription(account):
        raise PermissionDenied
    session = stripe.checkout.Session.create(
        client_reference_id=account.id,
        customer=account.stripe_customer_id or None,
        mode="setup",
        payment_method_types=["card"],
        success_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?install_complete=1",
        cancel_url=f"{settings.KODIAK_WEB_APP_URL}/t/{account.id}/usage?modify_subscription=1",
    )
    return JsonResponse(
        {
            "stripeCheckoutSessionId": session.id,
            "stripePublishableApiKey": settings.STRIPE_PUBLISHABLE_API_KEY,
        }
    )


@auth.login_required
def cancel_subscription(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)
    if not request.user.can_edit_subscription(account):
        raise PermissionDenied

    customer_info = account.stripe_customer_info()
    if customer_info is not None:
        customer_info.cancel_subscription()
    return HttpResponse(status=204)


@auth.login_required
@require_http_methods(["GET"])
def get_subscription_info(request: AuthedHttpRequest, team_id: str) -> JsonResponse:
    account = get_account_or_404(team_id=team_id, user=request.user)

    subscription_status = account.get_subscription_blocker()

    if subscription_status is not None:
        if subscription_status.kind == "trial_expired":
            return JsonResponse({"type": "TRIAL_EXPIRED"})

        if subscription_status.kind == "seats_exceeded":
            stripe_info = account.stripe_customer_info()
            license_count = 0
            if stripe_info and stripe_info.subscription_quantity:
                license_count = stripe_info.subscription_quantity
            active_user_count: int = len(
                UserPullRequestActivity.get_active_users_in_last_30_days(
                    account=account
                )
            )
            return JsonResponse(
                {
                    "type": "SUBSCRIPTION_OVERAGE",
                    "activeUserCount": active_user_count,
                    "licenseCount": license_count,
                }
            )

        if subscription_status.kind == "subscription_expired":
            return JsonResponse({"type": "SUBSCRIPTION_EXPIRED"})

    return JsonResponse({"type": "VALID_SUBSCRIPTION"})


def plan_id_from_period(period: Literal["month", "year"]) -> str:
    if period == "month":
        return cast(str, settings.STRIPE_PLAN_ID)
    if period == "year":
        return cast(str, settings.STRIPE_ANNUAL_PLAN_ID)
    return None


class FetchProrationModal(pydantic.BaseModel):
    subscriptionQuantity: int
    subscriptionPeriod: Literal["month", "year"] = "month"


@auth.login_required
def fetch_proration(request: AuthedHttpRequest, team_id: str) -> HttpResponse:
    payload = FetchProrationModal.parse_obj(request.POST.dict())
    account = get_account_or_404(user=request.user, team_id=team_id)

    stripe_plan_id = plan_id_from_period(period=payload.subscriptionPeriod)

    customer_info = account.stripe_customer_info()
    if customer_info is not None:
        proration_date = int(time.time())
        return JsonResponse(
            {
                "proratedCost": customer_info.preview_proration(
                    timestamp=proration_date,
                    subscription_quantity=payload.subscriptionQuantity,
                    plan_id=stripe_plan_id,
                ),
                "prorationTime": proration_date,
            }
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

    sentry_sdk.set_tag("stripe_event_type", event.type)
    logger.info("stripe_event_type=%s", event.type)

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
            account.update_customer(checkout_session.customer)
            stripe_customer_info = account.stripe_customer_info()
            if stripe_customer_info is None:
                logger.warning("expected account %s to have customer info", account)
                return HttpResponse(status=200)
            stripe_customer_info.update_from_stripe()
        elif checkout_session.mode == "subscription":
            # subscription occurs after a user creates a subscription through
            # the checkout.
            account = Account.objects.get(id=checkout_session.client_reference_id)
            account.update_customer(checkout_session.customer)

            try:
                stripe_customer_info = StripeCustomerInformation.objects.get(
                    customer_id=account.stripe_customer_id
                )
            except StripeCustomerInformation.DoesNotExist:
                stripe_customer_info = StripeCustomerInformation(
                    customer_id=account.stripe_customer_id
                )
            stripe_customer_info.update_from_stripe()
        else:
            raise BadRequest
        # Then define and call a method to handle the successful payment intent.
        # handle_payment_intent_succeeded(payment_intent)  # noqa: ERA001
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
        stripe_customer.update_from_stripe()
    elif event.type == "customer.subscription.deleted":
        StripeCustomerInformation.objects.filter(
            customer_id=event.data.object.customer
        ).delete()
    elif event.type == "invoice.payment_action_required":
        logger.warning("more action required for payment %s", event)
    elif event.type == "invoice.payment_failed":
        logger.warning("invoice.payment_failed %s", event)
    elif event.type == "customer.updated":
        stripe_customer_info = StripeCustomerInformation.objects.filter(
            customer_id=event.data.object.id
        ).first()
        if stripe_customer_info is None:
            logger.warning("customer.update event for unknown customer %s", event)
            raise BadRequest
        stripe_customer_info.update_from_stripe()

    elif event.type == "payment_method.attached":
        # a customer should only have one payment method.
        #
        # When a customer attaches a new payment method, remove the old ones to
        # ensure subscriptions use the newly added method.
        new_payment_method = event.data.object

        payment_methods = stripe.PaymentMethod.list(
            customer=new_payment_method.customer,
            type="card",
        )
        for payment_method in payment_methods.data:
            if payment_method.id != new_payment_method.id:
                stripe.PaymentMethod.detach(payment_method.id)

        stripe.Customer.modify(
            new_payment_method.customer,
            invoice_settings={"default_payment_method": new_payment_method.id},
        )
        stripe_customer_info = StripeCustomerInformation.objects.filter(
            customer_id=new_payment_method.customer
        ).first()
        if stripe_customer_info is None:
            logger.warning(
                "payment_method.attached event for unknown customer %s", event
            )
            raise BadRequest
        stripe_customer_info.update_from_stripe()

    else:
        logger.warning("unexpected event type %s", event.type)
        raise BadRequest

    return HttpResponse(status=200)


@auth.login_required
def accounts(request: AuthedHttpRequest) -> HttpResponse:
    return JsonResponse(
        [
            {
                "id": x.id,
                "name": x.github_account_login,
                "profileImgUrl": x.profile_image(),
            }
            for x in Account.objects.filter(memberships__user=request.user).order_by(
                "github_account_login"
            )
        ],
    )


def oauth_login(request: HttpRequest) -> HttpResponse:
    """
    Entry point to oauth flow.

    We keep this as a simple endpoint on the API to redirect users to from the
    frontend. This way we keep complexity within the API.

    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#1-request-a-users-github-identity
    """
    state = request.GET.get("state")
    if not state:
        return HttpResponseBadRequest("Missing required state parameter")
    oauth_url = URL("https://github.com/login/oauth/authorize").with_query(
        {
            "client_id": settings.KODIAK_API_GITHUB_CLIENT_ID,
            "redirect_uri": settings.KODIAK_WEB_AUTHED_LANDING_PATH,
            "state": state,
        }
    )
    return HttpResponseRedirect(str(oauth_url))


# TODO: handle deauthorization webhook
# https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#handling-a-revoked-github-app-authorization

# TODO: Handle installation event webhooks


@dataclass
class Error:
    error: str
    error_description: str
    ok: Literal[False] = False


@dataclass
class Success:
    ok: Literal[True] = True


def process_login_request(request: HttpRequest) -> Union[Success, Error]:
    session_oauth_state = request.POST.get("serverState", None)
    request_oauth_state = request.POST.get("clientState", None)
    if (
        not session_oauth_state
        or not request_oauth_state
        or session_oauth_state != request_oauth_state
    ):
        return Error(
            error="OAuthStateMismatch",
            error_description="State parameters must match.",
        )

    # handle errors
    if request.POST.get("error"):
        return Error(
            error=request.POST["error"],
            error_description=request.POST.get("error_description") or "",
        )

    code = request.POST.get("code")
    if not code:
        return Error(
            error="OAuthMissingCode",
            error_description="Payload should have a code parameter.",
        )

    payload = {
        "client_id": settings.KODIAK_API_GITHUB_CLIENT_ID,
        "client_secret": settings.KODIAK_API_GITHUB_CLIENT_SECRET,
        "code": code,
    }
    access_res = requests.post(
        "https://github.com/login/oauth/access_token", payload, timeout=5
    )
    try:
        access_res.raise_for_status()
    except (requests.HTTPError, requests.exceptions.Timeout):
        return Error(
            error="OAuthServerError", error_description="Failed to fetch access token."
        )
    access_res_data = dict(parse_qsl(access_res.text))
    access_token_error = access_res_data.get("error")
    if access_token_error:
        return Error(
            error=access_token_error,
            error_description=access_res_data.get("error_description", ""),
        )

    access_token = access_res_data.get("access_token")
    if not access_token:
        return Error(
            error="OAuthMissingAccessToken",
            error_description="OAuth missing access token.",
        )

    # fetch information about the user using their oauth access token.
    user_data_res = requests.get(
        "https://api.github.com/user",
        headers={"authorization": f"Bearer {access_token}"},
        timeout=5,
    )
    try:
        user_data_res.raise_for_status()
    except (requests.HTTPError, requests.exceptions.Timeout):
        return Error(
            error="OAuthServerError",
            error_description="Failed to fetch account information from GitHub.",
        )
    user_data = user_data_res.json()
    github_login = user_data["login"]
    github_account_id = int(user_data["id"])

    existing_user: Optional[User] = User.objects.filter(
        github_id=github_account_id
    ).first()
    if existing_user:
        existing_user.github_login = github_login
        existing_user.github_access_token = access_token
        existing_user.save()
        user = existing_user
    else:
        user = User.objects.create(
            github_id=github_account_id,
            github_login=github_login,
            github_access_token=access_token,
        )
    # TODO(chdsbd): Run this in as a background job if the user is an existing
    # user.
    try:
        user.sync_accounts()
    except SyncAccountsError:
        logger.warning("sync_accounts failed", exc_info=True)
        # ignore the errors if we were an existing user as we can use old data.
        if not existing_user:
            return Error(
                error="AccountSyncFailure",
                error_description="Failed to sync GitHub accounts for user.",
            )

    auth.login(user, request)
    return Success()


@require_http_methods(["POST", "OPTIONS"])
def oauth_complete(request: HttpRequest) -> HttpResponse:
    """
    OAuth callback handler from GitHub.
    We get a code from GitHub that we can use with our client secret to get an
    OAuth token for a GitHub user. The GitHub OAuth token only expires when the
    user uninstalls the app.
    https://developer.github.com/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps/#2-users-are-redirected-back-to-your-site-by-github
    """
    if request.method == "POST":
        login_result = process_login_request(request)
        return JsonResponse(asdict(login_result))
    return HttpResponse()


def logout(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    request.user = AnonymousUser()  # type: ignore [assignment]
    return HttpResponse(status=201)


@auth.login_required
@require_http_methods(["POST"])
def sync_accounts(request: AuthedHttpRequest) -> HttpResponse:
    try:
        request.user.sync_accounts()
    except SyncAccountsError:
        return JsonResponse({"ok": False})
    return JsonResponse({"ok": True})


def debug_sentry(request: HttpRequest) -> HttpResponse:
    return HttpResponse(1 / 0)
