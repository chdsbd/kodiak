from kodiak.event_handlers import get_branch_name


def test_get_branch_name() -> None:
    assert get_branch_name("refs/heads/master") == "master"
    assert (
        get_branch_name("refs/heads/master/refs/heads/123") == "master/refs/heads/123"
    )
    assert get_branch_name("refs/tags/v0.1.0") is None
