from __future__ import annotations

from typing import Any, TypeVar

_T = TypeVar("_T", bound="BoundLoggerBase")

class BoundLoggerBase:
    def __init__(self, logger: Any, processors: Any, context: Any) -> None: ...
    def bind(self: _T, **new_values: Any) -> _T: ...
    def unbind(self: _T, *keys: str) -> _T: ...
    def try_unbind(self: _T, *keys: str) -> _T: ...
    def new(self: _T, **new_values: Any) -> _T: ...
