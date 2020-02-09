import json
from pathlib import Path
from typing import Any, Dict, cast

import pydantic
import pytest
import toml

from kodiak.config import (
    V1,
    Approve,
    BodyText,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
    Update,
)


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


def test_config_default() -> None:
    file_path = load_config_fixture("v1-default.toml")
    loaded = toml.load(file_path)
    actual = V1.parse_obj(cast(Dict[Any, Any], loaded))
    expected = V1(version=1)

    assert actual == expected


@pytest.mark.parametrize(
    "config_fixture_name,expected_config",
    [
        (
            "v1-opposite.1.toml",
            V1(
                version=1,
                app_id="12345",
                merge=Merge(
                    automerge_label="mergeit!",
                    require_automerge_label=False,
                    blacklist_title_regex="",
                    blacklist_labels=["wip", "block-merge"],
                    method=MergeMethod.squash,
                    delete_branch_on_merge=True,
                    block_on_reviews_requested=True,
                    notify_on_conflict=False,
                    optimistic_updates=False,
                    dont_wait_on_status_checks=["ci/circleci: deploy"],
                    update_branch_immediately=True,
                    prioritize_ready_to_merge=True,
                    do_not_merge=True,
                    message=MergeMessage(
                        title=MergeTitleStyle.pull_request_title,
                        body=MergeBodyStyle.pull_request_body,
                        include_pr_number=False,
                        body_type=BodyText.plain_text,
                        strip_html_comments=True,
                    ),
                ),
                update=Update(always=True, require_automerge_label=False),
                approve=Approve(auto_approve_usernames=["dependabot"]),
            ),
        ),
        (
            "v1-opposite.2.toml",
            V1(
                version=1,
                app_id="12345",
                merge=Merge(
                    automerge_label="mergeit!",
                    require_automerge_label=False,
                    blacklist_title_regex="",
                    blacklist_labels=["wip", "block-merge"],
                    method=MergeMethod.squash,
                    delete_branch_on_merge=True,
                    block_on_reviews_requested=True,
                    notify_on_conflict=False,
                    optimistic_updates=False,
                    dont_wait_on_status_checks=["ci/circleci: deploy"],
                    update_branch_immediately=True,
                    prioritize_ready_to_merge=True,
                    do_not_merge=True,
                    message=MergeMessage(
                        title=MergeTitleStyle.pull_request_title,
                        body=MergeBodyStyle.empty,
                        include_pr_number=False,
                        body_type=BodyText.plain_text,
                        strip_html_comments=True,
                    ),
                ),
                update=Update(always=True, require_automerge_label=False),
                approve=Approve(auto_approve_usernames=["dependabot"]),
            ),
        ),
    ],
)
def test_config_parsing_opposite(config_fixture_name: str, expected_config: V1) -> None:
    """
    parse config with all opposite settings so we can ensure the config is
    correctly formatted.
    """
    file_path = load_config_fixture(config_fixture_name)
    loaded = toml.load(file_path)
    actual = V1.parse_obj(cast(Dict[Any, Any], loaded))

    assert actual == expected_config


def test_config_schema() -> None:
    schema_path = load_config_fixture("config-schema.json")
    assert json.loads(V1.schema_json()) == json.loads(
        schema_path.read_text()
    ), "schema shouldn't change unexpectedly."


def test_bad_file() -> None:
    res = V1.parse_toml("something[invalid[")
    assert isinstance(res, toml.TomlDecodeError)

    res = V1.parse_toml("version = 20")
    assert isinstance(res, pydantic.ValidationError)

    # we should return an error when we try to parse a different version
    res = V1.parse_toml("version = 20")
    assert isinstance(res, pydantic.ValidationError)

    # we should always require that the version is specified, even if we provide defaults for everything else
    res = V1.parse_toml("")
    assert isinstance(res, pydantic.ValidationError)

    res = V1.parse_toml("merge.automerge_label = 123")
    assert isinstance(res, pydantic.ValidationError)
