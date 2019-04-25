import pytest
from pathlib import Path
import json
import typing
import toml
import base64
from pathlib import Path

from .config import V1


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


@pytest.mark.parametrize("config, fixtures", [(V1, ["v1.toml", "v1.base64"])])
def test_config_parsing(config, fixtures: typing.List[str]):
    files = []
    for fixture_name in fixtures:
        file_path = load_config_fixture(fixture_name)
        if fixture_name.endswith(".base64"):
            loaded = toml.loads(base64.b64decode(file_path.read_bytes()).decode())
        elif fixture_name.endswith(".toml"):
            loaded = toml.load(file_path)
        else:
            raise Exception(f"Unhandled file: {fixture_name}")
        files.append(loaded)

    configs = [config.parse_obj(file) for file in files]
    for config in configs:
        assert config == configs[0], "all configs should be equal"
