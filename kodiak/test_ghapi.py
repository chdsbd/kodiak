import pytest
from requests_async.models import Response
import requests_async
from starlette.applications import Starlette
from unittest.mock import MagicMock
from pathlib import Path
from asyncio import Future

from .ghapi import get_contents, Content


contents = """
{
  "type": "file",
  "encoding": "base64",
  "size": 5362,
  "name": "README.md",
  "path": "README.md",
  "content": "encoded content ...",
  "sha": "3d21ec53a331a6f037a91c368710b99387d012c1",
  "url": "https://api.github.com/repos/octokit/octokit.rb/contents/README.md",
  "git_url": "https://api.github.com/repos/octokit/octokit.rb/git/blobs/3d21ec53a331a6f037a91c368710b99387d012c1",
  "html_url": "https://github.com/octokit/octokit.rb/blob/master/README.md",
  "download_url": "https://raw.githubusercontent.com/octokit/octokit.rb/master/README.md",
  "_links": {
    "git": "https://api.github.com/repos/octokit/octokit.rb/git/blobs/3d21ec53a331a6f037a91c368710b99387d012c1",
    "self": "https://api.github.com/repos/octokit/octokit.rb/contents/README.md",
    "html": "https://github.com/octokit/octokit.rb/blob/master/README.md"
  }
}
"""


def create_mock_response(content: str):
    res = Response()
    res.status_code = 200
    res._content = content.encode()
    future: Future[Response] = Future()
    future.set_result(res)
    return future


@pytest.mark.asyncio
async def test_get_contents(mocker):
    patched = mocker.patch("kodiak.ghapi.http.get")
    patched.return_value = create_mock_response(content=contents)
    config = await get_contents("octokit", "octokit.rb", "README.md")
    assert isinstance(config, Content)
