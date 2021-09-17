from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from asyncio_redis.encoders import BaseEncoder
from asyncio_redis.protocol import Transaction
from asyncio_redis.replies import (
    BlockingPopReply,
    BlockingZPopReply,
    DictReply,
    SetReply,
    StatusReply,
)

_Key = Union[bytes, str]

class Connection:
    @classmethod
    async def create(
        cls,
        host: str = ...,
        port: int = ...,
        *,
        password: Optional[Union[str, bytes]] = ...,
        db: int = ...,
        encoder: Optional[BaseEncoder] = ...,
        auto_reconnect: bool = ...,
        loop: Optional[Any] = ...,
        protocol_class: Any = ...,
        ssl: Optional[bool] = ...,
    ) -> Connection: ...
    def close(self) -> None: ...
    async def hgetall(self, key: _Key) -> DictReply: ...
    async def hset(self, key: _Key, field: _Key, value: _Key) -> int: ...
    async def delete(self, keys: List[_Key]) -> int: ...
    async def blpop(self, keys: List[_Key], timeout: int = ...) -> BlockingPopReply: ...
    async def bzpopmin(
        self, keys: List[_Key], timeout: int = ...
    ) -> BlockingZPopReply: ...
    async def get(self, key: _Key) -> Optional[str]: ...
    async def rpush(self, key: _Key, values: List[_Key]) -> int: ...
    async def ltrim(
        self, key: _Key, start: int = ..., stop: int = ...
    ) -> StatusReply: ...
    async def sadd(self, key: _Key, values: List[_Key]) -> int: ...
    async def expire(self, key: _Key, seconds: int) -> int: ...
    async def zrem(self, key: _Key, members: List[_Key]) -> int: ...
    async def zadd(
        self,
        key: _Key,
        values: Dict[str, Any],
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
        return_num_changed: bool = ...,
    ) -> int: ...
    async def set(
        self,
        key: _Key,
        value: _Key,
        expire: Optional[int] = ...,
        pexpire: Optional[int] = ...,
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
    ) -> Optional[StatusReply]: ...
    async def smembers(self, key: _Key) -> SetReply: ...
    async def multi(self) -> Transaction: ...

__all__ = ["Connection"]
