import typing
import requests_async as http
from enum import Enum
from pydantic import BaseModel, UrlStr
import base64
from starlette import status


class ContentEncoding(Enum):
    base64 = "base64"


class Content(BaseModel):
    name: str
    path: str
    sha: str
    size: int
    download_url: UrlStr
    type: str
    content: str
    encoding: ContentEncoding

    def decode(self) -> str:
        """
        Convert from encoding to str
        """
        if self.encoding == ContentEncoding.base64:
            return base64.b64decode(self.content).decode()
        raise TypeError()


class GithubAPIException(BaseException):
    pass


async def get_contents(org: str, repo: str, file: str) -> typing.Optional[Content]:
    # TODO: Add percent encoding, exception handling for api and parsing Content
    res = await http.get(f"https://api.github.com/repos/{org}/{repo}/contents/{file}")
    if res.status_code == status.HTTP_200_OK:
        return Content(**res.json())
    if res.status_code == status.HTTP_404_NOT_FOUND:
        return None
    else:
        raise GithubAPIException()
