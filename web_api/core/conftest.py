import pytest

from core.testutils import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient()
