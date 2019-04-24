import pytest
from pathlib import Path
import json
import toml

from .config import V1


@pytest.mark.parametrize("config, fixtures", [(V1, ["v1.toml"])])
def test_config_parsing(config, fixtures):
    for fixture_name in fixtures:
        loaded = toml.load(
            Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name
        )
        config.parse_obj(loaded)

