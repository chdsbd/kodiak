from typing import Any, AsyncIterator, Optional

import requests

from requests_async.models import Response

class Session(requests.Session):
    async def request(  # type: ignore [override]
        self, method: str, url: str, **kwargs: object
    ) -> Response: ...
    async def get(  # type: ignore [override]
        self, url: str, params: Optional[Any] = ..., **kwargs: object
    ) -> Response: ...
    async def options(  # type: ignore [override]
        self, url: str, **kwargs: object
    ) -> Response: ...
    async def head(  # type: ignore [override]
        self, url: str, **kwargs: object
    ) -> Response: ...
    async def post(  # type: ignore [override]
        self,
        url: str,
        data: Optional[Any] = ...,
        json: Optional[Any] = ...,
        **kwargs: object
    ) -> Response: ...
    async def put(  # type: ignore [override]
        self, url: str, data: Optional[Any] = ..., **kwargs: object
    ) -> Response: ...
    async def patch(  # type: ignore [override]
        self, url: str, data: Optional[Any] = ..., **kwargs: object
    ) -> Response: ...
    async def delete(  # type: ignore [override]
        self, url: str, **kwargs: object
    ) -> Response: ...
    async def __aiter__(self) -> AsyncIterator[bytes]: ...
    async def __aenter__(self) -> Session: ...
    async def __aexit__(self, *args: object) -> None: ...
    async def close(  # type: ignore [override]
        self
    ) -> None: ...

__all__ = ["Session"]
