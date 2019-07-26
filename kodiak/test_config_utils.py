from kodiak.config import V1

from .config_utils import get_markdown_for_config


def test_get_markdown_for_config():
    config = "version = 12"
    error = V1.parse_toml(config)
    markdown = get_markdown_for_config(error, config)
    assert markdown == ""
