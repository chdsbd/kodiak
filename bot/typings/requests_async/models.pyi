from typing import Optional, Union

from requests.models import PreparedRequest, Request
from requests.models import Response as BaseResponse
from typing_extensions import Literal

class Response(BaseResponse):
    _content: Optional[bytes]

__all__ = ["Response", "PreparedRequest", "Request"]
