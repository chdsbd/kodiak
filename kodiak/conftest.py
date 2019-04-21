import pytest
from starlette.testclient import TestClient
from kodiak.main import app


@pytest.fixture
def client():
    return TestClient(app)
