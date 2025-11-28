from typing import Any, Callable, Dict, Optional, Sequence

from typing_extensions import TypeAlias

_EventDict: TypeAlias = Dict[str, Any]

class KeyValueRenderer:
    def __init__(
        self,
        sort_keys: bool = ...,
        key_order: Optional[Sequence[str]] = ...,
        drop_missing: bool = ...,
        repr_native_str: bool = ...,
    ) -> None: ...
    def __call__(self, _: Any, __: Any, event_dict: _EventDict) -> Any: ...

class UnicodeEncoder:
    def __init__(self, encoding: str = ..., errors: str = ...) -> None: ...
    def __call__(
        self, logger: Any, name: str, event_dict: _EventDict
    ) -> _EventDict: ...

class UnicodeDecoder:
    def __init__(self, encoding: str = ..., errors: str = ...) -> None: ...
    def __call__(
        self, logger: Any, name: str, event_dict: _EventDict
    ) -> _EventDict: ...

class JSONRenderer:
    def __init__(
        self, serializer: Callable[..., str] = ..., **dumps_kw: Any
    ) -> None: ...
    def __call__(self, logger: Any, name: str, event_dict: _EventDict) -> str: ...

def format_exc_info(logger: Any, name: str, event_dict: _EventDict) -> _EventDict: ...

class TimeStamper: ...

class ExceptionPrettyPrinter:
    def __init__(self, file: Optional[Any] = ...) -> None: ...
    def __call__(
        self, logger: Any, name: str, event_dict: _EventDict
    ) -> _EventDict: ...

class StackInfoRenderer:
    def __call__(
        self, logger: Any, name: str, event_dict: _EventDict
    ) -> _EventDict: ...
