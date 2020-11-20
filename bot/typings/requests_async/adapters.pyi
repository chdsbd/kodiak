from typing import Any, Optional

from requests_async.models import Request, Response

class HTTPAdapter:
    async def send(
        self,
        request: Request,
        stream: bool = ...,
        timeout: Optional[int] = ...,
        verify: bool = ...,
        cert: Optional[Any] = ...,
        proxies: Optional[Any] = ...,
    ) -> Response: ...
    async def close(self) -> None: ...
    def build_response(self, req: Request, resp: Response) -> Response: ...

__all__ = ["HTTPAdapter"]
