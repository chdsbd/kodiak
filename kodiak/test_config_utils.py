from kodiak.config import V1

from .config_utils import get_markdown_for_config


def test_get_markdown_for_config_pydantic_error() -> None:
    config = "version = 12"
    error = V1.parse_toml(config)
    assert not isinstance(error, V1)
    markdown = get_markdown_for_config(
        error, config_str=config, git_path="master:.kodiak.toml"
    )
    assert markdown == ""


def test_get_markdown_for_config_toml_error() -> None:
    config = "[[[ version = 12"
    error = V1.parse_toml(config)
    assert not isinstance(error, V1)
    markdown = get_markdown_for_config(
        error, config_str=config, git_path="master:.kodiak.toml"
    )
    assert markdown == ""
