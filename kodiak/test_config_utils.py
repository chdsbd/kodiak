from pathlib import Path

from kodiak.config import V1
from kodiak.messages import get_markdown_for_config


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config_utils" / fixture_name


def test_get_markdown_for_config_pydantic_error() -> None:
    config = "version = 12"
    error = V1.parse_toml(config)
    assert not isinstance(error, V1)
    markdown = get_markdown_for_config(
        error, config_str=config, git_path="master:.kodiak.toml"
    )
    assert markdown == load_config_fixture("pydantic-error.md").read_text()


def test_get_markdown_for_config_toml_error() -> None:
    config = "[[[ version = 12"
    error = V1.parse_toml(config)
    assert not isinstance(error, V1)
    markdown = get_markdown_for_config(
        error, config_str=config, git_path="master:.kodiak.toml"
    )
    assert markdown == load_config_fixture("toml-error.md").read_text()
