from starlette.testclient import TestClient

from kodiak.main import get_branch_name


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


def test_get_branch_name() -> None:
    assert get_branch_name("refs/heads/master") == "master"
    assert (
        get_branch_name("refs/heads/master/refs/heads/123") == "master/refs/heads/123"
    )
    assert get_branch_name("refs/tags/v0.1.0") is None
