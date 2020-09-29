import pytest

from web_api.testutils import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient()
