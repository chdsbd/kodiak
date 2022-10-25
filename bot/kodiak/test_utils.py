import asyncio
import sys
from typing import TypeVar

T = TypeVar("T")

# some change happened in Python 3.8 to eliminate the need for wrapping mock
# results.
if sys.version_info < (3, 8):

    def wrap_future(x: T) -> "asyncio.Future[T]":
        fut: "asyncio.Future[T]" = asyncio.Future()
        fut.set_result(x)
        return fut

else:

    def wrap_future(x: T) -> "T":
        return x
