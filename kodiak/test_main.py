from starlette.testclient import TestClient

from .main import app


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"
