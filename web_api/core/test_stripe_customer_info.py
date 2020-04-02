from typing import Any

import pytest

from core.models import StripeCustomerInformation


@pytest.mark.django_db
def test_expired(mocker: Any) -> None:
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = 1650581784
    period_end = 1655765784 + ONE_DAY_SEC * 30  # start plus one month.
    mocker.patch("core.models.time.time", return_value=period_end + ONE_DAY_SEC * 3)
    stripe_customer_info = StripeCustomerInformation.objects.create(
        customer_id="cus_Ged32s2xnx12",
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

    assert stripe_customer_info.expired is True


@pytest.mark.django_db
def test_expired_inside_grace_period(mocker: Any) -> None:
    """
    Inside the grace period (two days) we will not show the subscription as
    expired.
    """
    ONE_DAY_SEC = 60 * 60 * 24
    period_start = 1650581784
    period_end = 1655765784 + 30 * ONE_DAY_SEC  # start plus one month.
    mocker.patch("core.models.time.time", return_value=period_end + ONE_DAY_SEC)
    stripe_customer_info = StripeCustomerInformation.objects.create(
        customer_id="cus_Ged32s2xnx12",
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

    assert stripe_customer_info.expired is False
