import pytest

from web_api.testutils import TestClient as Client


@pytest.mark.django_db
def test_health_check_middleware(client: Client) -> None:
    """
    smoke test for the health check endpoints
    """
    res = client.get("/healthz")
    assert res.status_code == 200
    res = client.get("/readiness")
    assert res.status_code == 200
