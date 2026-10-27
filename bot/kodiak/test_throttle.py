import asyncio

import pytest
from pytest_mock import MockFixture

from kodiak import throttle
from kodiak.http import Request, Response
from kodiak.queries import Client
from kodiak.throttle import Throttler, get_thottler_for_installation

INSTALLATION_ID = "8912353"


async def acquire(throttler: Throttler, count: int) -> None:
    for _ in range(count):
        await throttler.acquire()


async def test_throttler_hourly_limit_allows_bursts() -> None:
    """
    With a 15,000 request per hour limit we should be able to make a burst of
    requests without waiting. The default limit allows two per second.
    """
    throttler = Throttler(rate_limit=5000 / 60 / 60)
    throttler.set_hourly_limit(15_000)

    await asyncio.wait_for(acquire(throttler, 100), timeout=1)


async def test_throttler_hourly_limit_leaves_headroom() -> None:
    """
    We should stop before using GitHub's whole limit.
    """
    throttler = Throttler(rate_limit=5000 / 60 / 60)
    throttler.set_hourly_limit(600)  # 10 per minute, we use 8

    await asyncio.wait_for(acquire(throttler, 8), timeout=1)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquire(throttler, 1), timeout=0.1)


def rate_limited_response(*, url: str, resource: str, limit: str) -> Response:
    return Response(
        200,
        headers={"x-ratelimit-resource": resource, "x-ratelimit-limit": limit},
        request=Request(method="GET", url=url),
    )


@pytest.fixture(autouse=True)
def empty_throttler_cache(mocker: MockFixture) -> None:
    mocker.patch.dict(throttle.THROTTLER_CACHE, clear=True)


async def test_client_records_rate_limit_per_resource() -> None:
    """
    REST and GraphQL rate limits should update separate throttlers.
    """
    client = Client(installation_id=INSTALLATION_ID, owner="acme", repo="api")
    await client._record_rate_limit(
        rate_limited_response(
            url="https://api.github.com/graphql", resource="graphql", limit="10000"
        )
    )

    graphql = get_thottler_for_installation(
        installation_id=INSTALLATION_ID, resource="graphql"
    )
    rest = get_thottler_for_installation(installation_id=INSTALLATION_ID)
    await asyncio.wait_for(acquire(graphql, 100), timeout=1)
    await acquire(rest, 2)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquire(rest, 1), timeout=0.1)


async def test_client_ignores_app_rate_limit() -> None:
    """
    The token request is rate limited as our app, not the installation, so it
    shouldn't change the installation's throttler.
    """
    client = Client(installation_id=INSTALLATION_ID, owner="acme", repo="api")
    await client._record_rate_limit(
        rate_limited_response(
            url=f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens",
            resource="core",
            limit="15000",
        )
    )

    rest = get_thottler_for_installation(installation_id=INSTALLATION_ID)
    await acquire(rest, 2)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquire(rest, 1), timeout=0.1)
