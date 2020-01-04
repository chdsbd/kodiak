from starlette.testclient import TestClient


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"
