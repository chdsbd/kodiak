from __future__ import annotations

from typing import Any, Mapping, Optional

from typing_extensions import Literal

class RequestsMock:
    def __enter__(self) -> RequestsMock: ...
    def __exit__(self, type: object, value: object, traceback: object) -> bool: ...
    def add(
        self,
        method: Optional[Literal["GET", "POST"]] = None,
        url: Optional[str] = None,
        body: str = "",
        adding_headers: Optional[Mapping[str, str]] = None,
        json: Optional[Mapping[str, Any]] = None,
        status: Optional[int] = None,
        content_type: Optional[str] = None,
    ) -> None: ...

GET: Literal["GET"]
POST: Literal["POST"]
