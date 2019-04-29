import pytest
from pathlib import Path
import typing
import toml
from pathlib import Path
import toml

from kodiak.config import V1


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


@pytest.mark.parametrize("config, fixtures", [(V1, ["v1.toml"])])
def test_config_parsing(config, fixtures: typing.List[str]):
    files = []
    for fixture_name in fixtures:
        file_path = load_config_fixture(fixture_name)
        loaded = toml.load(file_path)
        files.append(loaded)

    configs = [config.parse_obj(file) for file in files]
    for config in configs:
        assert config == configs[0], "all configs should be equal"


def test_bad_file():
    res = V1.parse_toml("something[invalid[")
    assert isinstance(res, toml.TomlDecodeError)
