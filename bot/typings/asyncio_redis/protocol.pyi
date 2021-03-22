from typing import Any, Awaitable, Dict, List, Optional, Union

from asyncio_redis.replies import StatusReply, ZRangeReply

_Key = Union[bytes, str]

class Transaction:
    async def expire(self, key: _Key, seconds: int) -> Awaitable[int]: ...
    async def zadd(
        self,
        key: _Key,
        values: Dict[str, Any],
        only_if_not_exists: bool = ...,
        only_if_exists: bool = ...,
        return_num_changed: bool = ...,
    ) -> Awaitable[int]: ...
    async def sadd(self, key: _Key, values: List[_Key]) -> Awaitable[int]: ...
    async def zrange(
        self, key: _Key, start: int = ..., stop: int = ...
    ) -> Awaitable[ZRangeReply]: ...
    async def set(
        self,
        key: _Key,
        value: _Key,
        expire: Optional[int] = ...,
        pexpire: Optional[int] = ...,
        only_if_not_exists: bool = False,
        only_if_exists: bool = False,
    ) -> Awaitable[Optional[StatusReply]]: ...
    async def exec(self) -> None: ...

__all__ = ["Transaction"]
