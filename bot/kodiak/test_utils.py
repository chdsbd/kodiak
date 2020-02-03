import asyncio
from typing import TypeVar

T = TypeVar("T")


def wrap_future(x: T) -> "asyncio.Future[T]":
    fut: "asyncio.Future[T]" = asyncio.Future()
    fut.set_result(x)
    return fut
