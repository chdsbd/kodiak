import pytest
import stripe
from pytest_mock import MockFixture

from core.models import Account, AccountMembership, User
from core.testutils import TestClient as Client


@pytest.mark.django_db
def test_stripe_self_serve_redirect_view(mocker: MockFixture) -> None:
    """
    Smoke test to ensure the redirect URL for the stripe billing portal works
    in the success case.
    """
    fake_billing_portal_session = stripe.billing_portal.Session.construct_from(
        {
            "created": 1588895592,
            "customer": "cus_HEmOJM4AntPHdz",
            "id": "bps_1GgJWeCoyKa1V9Y6Bfnab1L3",
            "livemode": False,
            "object": "billing_portal.session",
            "return_url": "http://app.localhost.kodiakhq.com:3000/t/134f9ff9-327b-4cb3-a0b3-edf63f23a96e/usage",
            "url": "https://billing.stripe.com/session/O4pTob2jXrlVdYdh1grBH1mXJiOIDgwS",
        },
        "fake-key",
    )

    mocker.patch(
        "core.views.stripe.billing_portal.Session.create",
        return_value=fake_billing_portal_session,
    )

    user = User.objects.create(
        github_id=10137,
        github_login="ghost",
        github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
    )
    account = Account.objects.create(
        github_installation_id=377930,
        github_account_id=900966,
        github_account_login=user.github_login,
        github_account_type="User",
    )
    AccountMembership.objects.create(account=account, user=user, role="member")

    client = Client()
    client.login(user)
    res = client.get(f"/v1/t/{account.id}/stripe_self_serve_redirect")

    assert res.status_code == 302
    assert res["Location"] == fake_billing_portal_session.url
