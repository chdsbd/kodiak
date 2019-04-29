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

    res = V1.parse_toml("version = 20")
    assert isinstance(
        res, ValueError
    ), "we should raise an error when we try to parse a different version"

    res = V1.parse_toml("")
    assert isinstance(
        res, ValueError
    ), "we should always require that the version is specified, even if we provide defaults for everything else"

    res = V1.parse_toml("merge.whitelist = [123]")
    assert isinstance(res, ValueError)
