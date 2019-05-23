import pytest
from pathlib import Path
import typing
import toml

from kodiak.config import V1


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


@pytest.mark.parametrize("config, fixtures", [(V1, ["v1.toml"])])
def test_config_parsing(config: V1, fixtures: typing.List[str]) -> None:
    files = []
    for fixture_name in fixtures:
        file_path = load_config_fixture(fixture_name)
        loaded = toml.load(file_path)
        files.append(loaded)

    configs = [
        config.parse_obj(typing.cast(typing.Dict[typing.Any, typing.Any], file))
        for file in files
    ]
    for cfg in configs:
        assert cfg == configs[0], "all configs should be equal"


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
        V1.parse_toml("merge.whitelist = [123]")
