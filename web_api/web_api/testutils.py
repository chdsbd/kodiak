from importlib import import_module
from typing import Optional, Tuple, Type, Union, cast

import stripe
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase as SessionStore
from django.http import HttpRequest, SimpleCookie
from django.test.client import Client as DjangoTestClient
from typing_extensions import Literal

from web_api import auth
from web_api.models import Account, AccountMembership, StripeCustomerInformation, User


class TestClient(DjangoTestClient):
    def login(self, user: User) -> None:
        engine: SessionStore = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        auth.login(user, request)

        # Save the session values.
        request.session.save()

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            "max-age": None,
            "path": "/",
            "domain": settings.SESSION_COOKIE_DOMAIN,
            "secure": settings.SESSION_COOKIE_SECURE or None,
            "expires": None,
        }
        self.cookies[session_cookie].update(cookie_data)

    def logout(self) -> None:
        """Log out the user by removing the cookies and session object."""
        request = HttpRequest()
        engine: SessionStore = import_module(settings.SESSION_ENGINE)
        if self.session:
            request.session = self.session
            request.user = auth.get_user(request)
        else:
            request.session = engine.SessionStore()
        auth.logout(request)
        self.cookies = SimpleCookie()


PRIMARY_KEYS = iter(range(1000, 100000))


def create_pk() -> int:
    return next(PRIMARY_KEYS)


def create_account(
    *,
    stripe_customer_id: str = "cus_523405923045",
    github_account_login: str = "acme-corp",
    github_account_type: Literal["User", "Organization"] = "User",
) -> Account:

    return cast(
        Account,
        Account.objects.create(
            github_installation_id=create_pk(),
            github_account_id=create_pk(),
            github_account_login=github_account_login,
            github_account_type=github_account_type,
            stripe_customer_id=stripe_customer_id,
        ),
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
    return cast(
        StripeCustomerInformation,
        StripeCustomerInformation.objects.create(
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan_id="plan_G2df31A4G5JzQ",
            customer_email="accounting@acme-corp.com",
            customer_balance=0,
            customer_created=1585781308,
            plan_amount=499,
            plan_interval="month",
            subscription_quantity=3,
            subscription_start_date=1585781784,
            upcoming_invoice_total=1122,
            subscription_current_period_start=subscription_current_period_start,
            subscription_current_period_end=subscription_current_period_end,
        ),
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


def create_stripe_product() -> stripe.PaymentMethod:
    return stripe.Product.construct_from(
        dict(
            active=True,
            attributes=[],
            created=1584327796,
            description=None,
            id="prod_GuzCMVKonQIp2l",
            images=[],
            livemode=False,
            metadata={},
            name="Kodiak Seat License",
            object="product",
            statement_descriptor=None,
            type="service",
            unit_label="seat",
            updated=1602001699,
        ),
        "fake-key",
    )


def create_stripe_invoice() -> stripe.PaymentMethod:
    return stripe.Invoice.construct_from(
        dict(
            collection_method="charge_automatically",
            created=1604199554,
            discounts=["di_1HYCfYCoyKa1V9Y6KoYbNjUl"],
            object="invoice",
            subscription="sub_HwIIwYw13iV6Jk",
            subtotal=1996,
            total=998,
        ),
        "fake-key",
    )


class Unset:
    pass


def create_stripe_customer(
    *,
    id: str = "cus_Gz7jQFKdh4KirU",
    email: str = "accounting@acme.corp",
    name: Optional[str] = None,
    address: Optional[Union[dict, Type[Unset]]] = Unset,
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
            email=email,
            name=name,
            subscriptions=dict(data=[dict(id="sub_Gu1xedsfo1")]),
        ),
        "fake-key",
    )


def create_stripe_subscription(
    interval: Literal["month", "year"] = "month",
    cancel_at: Optional[int] = None,
    canceled_at: Optional[int] = None,
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
                product="prod_GuzCMVKonQIp2l",
            ),
            cancel_at=cancel_at,
            canceled_at=canceled_at,
            quantity=4,
            start_date=1443556775,
            default_payment_method="pm_22dldxf3",
        ),
        "fake-key",
    )
