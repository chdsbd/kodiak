import pytest
from pathlib import Path
import json
import asyncio

from kodiak.queries import Client


@pytest.mark.asyncio
async def test_generate_jwt(private_key: str):
    async with Client(private_key=private_key, app_identifier="29196") as api:
        assert api.generate_jwt() is not None
