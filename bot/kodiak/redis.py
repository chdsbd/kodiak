from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Iterator, Protocol, Union

import asyncio_redis
from asyncio_redis.exceptions import ConnectionLostError

from kodiak import app_config as conf

_Key = Union[str, bytes]


class BlockingZPopReply(Protocol):
    @property
    def value(self) -> bytes:
        ...

    @property
    def score(self) -> float:
        ...


class StatusReply(Protocol):
    ...


class SetReply(Protocol):
    def __iter__(self) -> Iterator[Awaitable[str]]:
        ...


class ZRangeReply(Protocol):
    async def asdict(self) -> dict[bytes, bytes]:
        ...


class Transaction(Protocol):
    async def expire(self, key: _Key, seconds: int) -> Awaitable[int]:
        ...

    async def zadd(
        self,
        key: _Key,
        values: dict[str, Any],
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
        return_num_changed: bool = ...,
    ) -> Awaitable[int]:
        ...

    async def sadd(self, key: _Key, values: list[_Key]) -> Awaitable[int]:
        ...

    async def zrange(
        self, key: _Key, start: int = ..., stop: int = ...
    ) -> Awaitable[ZRangeReply]:
        ...

    async def set(
        self,
        key: _Key,
        value: _Key,
        expire: int | None = ...,
        pexpire: int | None = ...,
        only_if_not_exists: bool = False,
        only_if_exists: bool = False,
    ) -> Awaitable[StatusReply | None]:
        ...

    async def exec(self) -> None:
        ...


class Connection(Protocol):
    async def get(self, key: _Key) -> str | None:
        ...

    async def bzpopmin(self, keys: list[_Key], timeout: int = ...) -> BlockingZPopReply:
        ...

    async def zrem(self, key: _Key, members: list[_Key]) -> int:
        ...

    async def zadd(
        self,
        key: _Key,
        values: dict[str, Any],
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
        return_num_changed: bool = ...,
    ) -> int:
        ...

    async def delete(self, keys: list[_Key]) -> int:
        ...

    async def smembers(self, key: _Key) -> SetReply:
        ...

    async def set(
        self,
        key: _Key,
        value: _Key,
        expire: int | None = ...,
        pexpire: int | None = ...,
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
    ) -> StatusReply | None:
        ...

    async def multi(self) -> Transaction:
        ...


class RobustConnection:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    async def get(self, key: _Key) -> str | None:
        retry_count = 5
        while retry_count:
            try:
                return await self._connection.get(key=key)
            except ConnectionLostError:
                if retry_count <= 0:
                    raise
                retry_count -= 1
                await asyncio.sleep(0.2)
        raise Exception("shouldn't get here")

    async def bzpopmin(self, keys: list[_Key], timeout: int = 0) -> BlockingZPopReply:
        return await self._connection.bzpopmin(keys=keys, timeout=timeout)

    async def zrem(self, key: _Key, members: list[_Key]) -> int:
        return await self._connection.zrem(key=key, members=members)

    async def zadd(
        self,
        key: _Key,
        values: dict[str, Any],
        only_if_not_exists: bool = False,
        only_if_exists: bool = False,
        return_num_changed: bool = False,
    ) -> int:
        return await self._connection.zadd(
            key=key,
            values=values,
            only_if_not_exists=only_if_not_exists,
            only_if_exists=only_if_exists,
            return_num_changed=return_num_changed,
        )

    async def delete(self, keys: list[_Key]) -> int:
        return await self._connection.delete(keys=keys)

    async def smembers(self, key: _Key) -> SetReply:
        return await self._connection.smembers(key=key)

    async def set(
        self,
        key: _Key,
        value: _Key,
        expire: int | None = None,
        pexpire: int | None = None,
        only_if_not_exists: bool = False,
        only_if_exists: bool = False,
    ) -> StatusReply | None:
        return await self._connection.set(
            key, value, expire, pexpire, only_if_not_exists, only_if_exists
        )

    async def multi(self) -> Transaction:
        return await self._connection.multi()


async def create_pool() -> Connection:
    redis_db = 0
    try:
        redis_db = int(conf.REDIS_URL.database)
    except ValueError:
        pass
    conn = await asyncio_redis.Pool.create(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=conf.REDIS_URL.password or None,
        db=redis_db,
        poolsize=conf.REDIS_POOL_SIZE,
        ssl=conf.REDIS_URL.scheme == "rediss",
    )

    return RobustConnection(conn)
