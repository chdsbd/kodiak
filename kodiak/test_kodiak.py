import typing
import pytest
from kodiak import get_config
from kodiak.config import V1
from requests_async.models import Response
import requests_async
from starlette.applications import Starlette
from unittest.mock import MagicMock
from pathlib import Path
from kodiak.ghapi import Content


def create_mock_response_callable(res: typing.Any):
    class AsyncMock(MagicMock):
        async def __call__(self, *args, **kwargs):
            return res

    return AsyncMock


def load_config_fixture(fixture_name: str) -> Path:
    return Path(__file__).parent / "test" / "fixtures" / "config" / fixture_name


@pytest.fixture
def content():
    return Content(
        name="config.toml",
        path="config.toml",
        sha="abc",
        size=100,
        download_url="http://example.com/config.toml",
        type="base64",
        content=load_config_fixture("v1.base64").read_bytes(),
        encoding="base64",
    )


@pytest.mark.asyncio
async def test_get_config(mocker, content: Content):

    patched = mocker.patch(
        "kodiak.ghapi.get_contents",
        new_callable=create_mock_response_callable(res=None),
    )
    config = await get_config("palantir", "bulldozer")
    assert config is None
    patched = mocker.patch(
        "kodiak.ghapi.get_contents",
        new_callable=create_mock_response_callable(res=content),
    )
    config = await get_config("palantir", "bulldozer")
    assert isinstance(config, V1)
