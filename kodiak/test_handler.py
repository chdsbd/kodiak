from kodiak.handler import create_git_revision_expression


def test_create_git_revision_expression():
    assert (
        create_git_revision_expression("master", ".github/.kodiak.toml")
        == "master:.github/.kodiak.toml"
    )


def test_find_event_data():
    assert False


def test_merge_pr():
    assert False


def test_root_handler():
    assert False
