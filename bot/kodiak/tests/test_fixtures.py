import pytest

from kodiak.queries import ThrottlerProtocol
from kodiak.tests.fixtures import FakeThottler


@pytest.mark.asyncio
async def test_fake_throttler() -> None:
    throttler: ThrottlerProtocol = FakeThottler()
    async with throttler:
        pass
