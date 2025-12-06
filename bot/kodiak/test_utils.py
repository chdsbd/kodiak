from typing import TypeVar

T = TypeVar("T")


def wrap_future(x: T) -> "T":
    return x
