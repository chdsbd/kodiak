from pathlib import Path
from typing import Any, Dict, cast

import pytest
import toml

from kodiak.config import (
    V1,
    BodyText,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
)


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


def test_config_default() -> None:
    file_path = load_config_fixture("v1-default.toml")
    loaded = toml.load(file_path)
    actual = V1.parse_obj(cast(Dict[Any, Any], loaded))
    expected = V1(version=1)

    assert actual == expected


def test_config_parsing_opposite() -> None:
    """
    parse config with all opposite settings so we can ensure the config is
    correctly formatted.
    """
    file_path = load_config_fixture("v1-opposite.toml")
    loaded = toml.load(file_path)
    actual = V1.parse_obj(cast(Dict[Any, Any], loaded))

    expected = V1(
        version=1,
        app_id="12345",
        merge=Merge(
            automerge_label="mergeit!",
            blacklist_title_regex="",
            blacklist_labels=["wip", "block-merge"],
            method=MergeMethod.squash,
            delete_branch_on_merge=True,
            block_on_reviews_requested=True,
            notify_on_conflict=False,
            optimistic_updates=False,
            message=MergeMessage(
                title=MergeTitleStyle.pull_request_title,
                body=MergeBodyStyle.pull_request_body,
                include_pr_number=False,
                body_type=BodyText.plain_text,
                strip_html_comments=True
            ),
        ),
    )

    assert actual == expected


def test_bad_file() -> None:
    with pytest.raises(toml.TomlDecodeError):
        V1.parse_toml("something[invalid[")

    with pytest.raises(ValueError):
        # we should raise an error when we try to parse a different version
        V1.parse_toml("version = 20")

    with pytest.raises(ValueError):
        # we should always require that the version is specified, even if we provide defaults for everything else
        V1.parse_toml("")

    with pytest.raises(ValueError):
        V1.parse_toml("merge.automerge_label = 123")
