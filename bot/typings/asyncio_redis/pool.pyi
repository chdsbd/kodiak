from typing import Any, Dict, List, Optional, Union

from asyncio_redis.connection import Subscription
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

class Pool:
    @classmethod
    async def create(
        cls,
        host: str = ...,
        port: int = ...,
        *,
        password: Optional[Union[str, bytes]] = ...,
        db: int = ...,
        encoder: Optional[BaseEncoder] = ...,
        poolsize: int = ...,
        auto_reconnection: bool = ...,
        loop: Optional[Any] = ...,
        protocol_class: Any = ...,
        ssl: Optional[bool] = ...,
        # false positive, see: https://github.com/charliermarsh/ruff/issues/1613
    ) -> Pool: ...  # noqa: F821
    # NOTE(sbdchd): asyncio_redis does some hackery with __getattr__, so we copy
    # the methods from Connection
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
    async def llen(self, key: _Key) -> int: ...
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
    async def publish(self, channel: _Key, message: _Key) -> int: ...
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
    async def start_subscribe(self) -> Subscription: ...
    async def multi(self) -> Transaction: ...

__all__ = ["Pool"]
