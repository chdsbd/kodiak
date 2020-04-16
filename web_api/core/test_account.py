import pytest
import redis
from django.conf import settings

from core.models import Account


@pytest.mark.django_db
def test_update_bot() -> None:
    """
    Should update subscription information in Redis
    """
    r = redis.Redis.from_url(settings.REDIS_URL)
    r.flushdb()
    account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login="acme-corp",
        github_account_id=523412234,
        github_account_type="Organization",
    )
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {}  # type: ignore
    account.update_bot()
    assert r.hgetall(f"kodiak:subscription:{account.github_installation_id}") == {  # type: ignore
        b"account_id": str(account.id).encode(),
        b"subscription_blocker": b"",
    }
