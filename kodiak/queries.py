import typing
import os
from mypy_extensions import TypedDict
from starlette import status
from dataclasses import dataclass
from requests_async import Response
import requests_async as http


class ErrorLocation(TypedDict):
    line: int
    column: int


class GraphQLError(TypedDict):
    message: str
    locations: typing.List[ErrorLocation]
    type: typing.Optional[str]
    path: typing.Optional[typing.List[str]]


class GraphQLResponse(TypedDict):
    data: typing.Optional[typing.Dict[typing.Any, typing.Any]]
    errors: typing.Optional[typing.List[GraphQLError]]


@dataclass
class QueryError(BaseException):
    response: Response


DEFAULT_BRANCH_NAME_QUERY = """
query ($owner: String!, $repo: String!) {  repository(owner: $owner, name: $repo) {    defaultBranchRef {      name    }  }}
"""


@dataclass
class BranchNameError(BaseException):
    res: GraphQLResponse


class Client:
    token: typing.Optional[str]
    session: http.Session
    entered: bool = False

    def __init__(self, token: typing.Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        assert (
            self.token is not None
        ), "missing token. Github's GraphQL endpoint requires authentication."
        # NOTE: We must call `await session.close()` when we are finished with our session.
        # We implement an async context manager this handle this.
        self.session = http.Session()
        self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers[
            "Accept"
        ] = "application/vnd.github.antiope-preview+json,application/vnd.github.merge-info-preview+json"

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.session.close()

    async def send_query(
        self, query: str, variables: typing.Mapping[str, str]
    ) -> GraphQLResponse:
        assert (
            self.entered
        ), "Client must be used in an async context manager. `async with Client() as api: ..."
        res = await self.session.post(
            "https://api.github.com/graphql",
            json=(dict(query=query, variables=variables)),
        )
        if res.status_code != status.HTTP_200_OK:
            raise QueryError(response=res)
        return typing.cast(GraphQLResponse, res.json())

    async def get_default_branch_name(self, owner: str, repo: str) -> str:
        res = await self.send_query(
            query=DEFAULT_BRANCH_NAME_QUERY, variables=dict(owner=owner, repo=repo)
        )
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            raise BranchNameError(res=res)
        return typing.cast(str, data["repository"]["defaultBranchRef"]["name"])
