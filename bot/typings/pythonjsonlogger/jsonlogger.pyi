import json
import logging
from typing import Any, Callable, Dict, Iterable, Mapping

from typing_extensions import Literal

RESERVED_ATTRS: tuple[str]

_LogRecord = Dict[str, Any]
_FormatStyle = Literal["%", "{", "$"]

def merge_record_extra(
    record: logging.LogRecord,
    target: dict[str, Any],
    reserved: dict[str, Any] | list[str],
) -> dict[str, Any] | list[str]: ...

class JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> str: ...
    def format_datetime_obj(self, obj: Any) -> str: ...

class JsonFormatter(logging.Formatter):
    def __init__(
        self,
        fmt: str | None = ...,
        datefmt: str | None = ...,
        style: _FormatStyle = ...,
        validate: bool = ...,
        *,
        json_default: Callable[[Any], Any] | None = ...,
        json_encoder: json.JSONEncoder | None = ...,
        json_serializer: Callable[[Any], str] = ...,
        json_indent: int | None = ...,
        json_ensure_ascii: bool = ...,
        prefix: str = ...,
        rename_fields: Mapping[str, str] = ...,
        static_fields: Mapping[str, Any] = ...,
        reserved_attrs: Iterable[str] = ...,
        timestamp: str | bool = ...,
    ) -> None: ...
    def _str_to_fn(self, fn_as_str: Any) -> Any: ...
    def parse(self) -> list[Any]: ...
    def add_fields(
        self,
        log_record: _LogRecord,
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None: ...
    def process_log_record(self, log_record: _LogRecord) -> logging.LogRecord: ...
    def jsonify_log_record(self, log_record: _LogRecord) -> str: ...
    def serialize_log_record(self, log_record: _LogRecord) -> str: ...
    def format(self, record: logging.LogRecord) -> str: ...
