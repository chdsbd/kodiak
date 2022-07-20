import pytest
import structlog
from asyncio_redis.exceptions import ConnectionLostError
from pytest_mock import MockFixture

from kodiak.queue import create_pool, installation_id_from_queue
from kodiak.tests.fixtures import requires_redis

logger = structlog.get_logger()


@pytest.mark.parametrize(
    "queue_name, expected_installation_id",
    (
        ("merge_queue:11256551.sbdchd/squawk/main.test.foo", "11256551"),
        ("merge_queue:11256551.sbdchd/squawk", "11256551"),
        ("merge_queue:11256551.sbdchd/squawk:repo/main:test.branch", "11256551"),
        ("webhook:11256551", "11256551"),
        ("", ""),
    ),
)
def test_installation_id_from_queue(
    queue_name: str, expected_installation_id: str
) -> None:
    """
    We should gracefully parse an installation id from the queue name
    """
    assert installation_id_from_queue(queue_name) == expected_installation_id


@requires_redis
@pytest.mark.asyncio
async def test_flakey_redis_success(mocker: MockFixture) -> None:
    """
    Checking our redis retry logic
    """

    pool = await create_pool()

    cnt = 2

    async def wrapper() -> None:
        logger.info("attemping ping")
        nonlocal cnt
        cnt -= 1
        if cnt <= 0:
            logger.info("ping success!")
            return
        raise ConnectionLostError("foo")

    mocker.patch.object(pool._pool, "ping", wraps=wrapper)

    async with pool as conn:
        await conn.ping()


@requires_redis
@pytest.mark.asyncio
async def test_flakey_redis_failure(mocker: MockFixture) -> None:
    """
    Checking our redis retry logic when it fails
    """

    pool = await create_pool()

    cnt = 6

    async def wrapper() -> None:
        logger.info("attemping ping")
        nonlocal cnt
        cnt -= 1
        if cnt <= 0:
            logger.info("ping success!")
            return
        raise ConnectionLostError("foo")

    mocker.patch.object(pool._pool, "ping", wraps=wrapper)

    with pytest.raises(ConnectionLostError):
        async with pool as conn:
            await conn.ping()
