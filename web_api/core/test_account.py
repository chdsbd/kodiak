import pytest
from core.models import Account

@pytest.mark.django_db
def test_update_bot():
    """
    Should update subscription information in Redis
    """
    account.update_bot()
    assert False

# TODO: Ensure we call this when we start trials, create/update/delete subscriptions, get webhooks from Stripe
