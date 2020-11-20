from typing import Awaitable, Dict, Iterator

class DictReply:
    async def asdict(self) -> Dict[bytes, bytes]: ...

class StatusReply: ...
class ZRangeReply(DictReply): ...

class BlockingPopReply:
    @property
    def value(self) -> bytes: ...

class SetReply:
    def __iter__(self) -> Iterator[Awaitable[str]]: ...

class BlockingZPopReply:
    @property
    def value(self) -> bytes: ...

__all__ = ["DictReply", "BlockingZPopReply", "StatusReply"]
