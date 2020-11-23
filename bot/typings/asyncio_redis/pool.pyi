from typing import Any, Optional, Union

from asyncio_redis.connection import Connection
from asyncio_redis.encoders import BaseEncoder

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
        protocol_class: Any = ...
    ) -> Connection: ...

__all__ = ["Pool"]
