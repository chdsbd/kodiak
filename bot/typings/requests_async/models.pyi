from typing import Union

from requests.models import PreparedRequest, Request
from requests.models import Response as BaseResponse
from typing_extensions import Literal

class Response(BaseResponse):
    _content: Union[bytes, None, Literal[False]]  # type: ignore [assignment]

__all__ = ["Response", "PreparedRequest", "Request"]
