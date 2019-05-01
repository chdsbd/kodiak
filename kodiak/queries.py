import os
import typing
from dataclasses import dataclass
from enum import Enum
import structlog
from pathlib import Path

import requests_async as http
from mypy_extensions import TypedDict
from requests_async import Response
from starlette import status
from jsonpath_rw import parse
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt

log = structlog.get_logger()


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
class ServerError(BaseException):
    response: Response


DEFAULT_BRANCH_NAME_QUERY = """
query ($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef {
      name
    }
  }
}
"""


@dataclass
class ResponseError(BaseException):
    res: GraphQLResponse


class BranchNameError(ResponseError):
    pass


GET_EVENT_INFO_QUERY = """
query GetEventInfo($owner: String!, $repo: String!, $configFileExpression: String!, $PRNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    mergeCommitAllowed
    rebaseMergeAllowed
    squashMergeAllowed
    pullRequest(number: $PRNumber) {
      id
      mergeStateStatus
      state
      commits(last: 1) {
        nodes {
          commit {
            oid
          }
        }
      }
      labels(first: 100) {
        nodes {
          name
        }
        totalCount
      }
    }
    object(expression: $configFileExpression) {
      ... on Blob {
        text
      }
    }
  }
}

"""


class MergeStateStatus(Enum):
    # The head ref is out of date.
    BEHIND = "BEHIND"
    # The merge is blocked.
    BLOCKED = "BLOCKED"
    # Mergeable and passing commit status.
    CLEAN = "CLEAN"
    # The merge commit cannot be cleanly created.
    DIRTY = "DIRTY"
    # The merge is blocked due to the pull request being a draft.
    DRAFT = "DRAFT"
    # Mergeable with passing commit status and pre-recieve hooks.
    HAS_HOOKS = "HAS_HOOKS"
    # The state cannot currently be determined.
    UNKNOWN = "UNKNOWN"
    # Mergeable with non-passing commit status.
    UNSTABLE = "UNSTABLE"


class PullRequestState(Enum):
    # A pull request that is still open.
    OPEN = "OPEN"
    # A pull request that has been closed without being merged.
    CLOSED = "CLOSED"
    # A pull request that has been closed by being merged.
    MERGED = "MERGED"


class PullRequest(BaseModel):
    id: str
    mergeStateStatus: MergeStateStatus
    state: PullRequestState
    labels: typing.List[str]
    # the SHA of the most recent commit
    latest_sha: str


@dataclass
class RepoInfo:
    merge_commit_allowed: bool
    rebase_merge_allowed: bool
    squash_merge_allowed: bool


@dataclass
class EventInfoResponse:
    config_file: typing.Optional[str]
    pull_request: typing.Optional[PullRequest]
    repo: typing.Optional[RepoInfo]


class EventInfoError(ResponseError):
    pass


def get_values(expr: str, data: typing.Dict) -> typing.List[typing.Any]:
    return [match.value for match in parse(expr).find(data)]


def get_value(expr: str, data: typing.Dict) -> typing.Optional[typing.Any]:
    return next(iter(get_values(expr, data)), None)


MERGE_PR_MUTATION = """
mutation merge($PRId: ID!, $SHA: GitObjectID!, $title: String, $body: String) {
  mergePullRequest(input: {pullRequestId: $PRId, expectedHeadOid: $SHA, commitHeadline: $title, commitBody: $body}) {
    clientMutationId
  }
}

"""


class Client:
    token: typing.Optional[str]
    session: http.Session
    entered: bool = False
    private_key: typing.Optional[str]
    private_key_path: typing.Optional[Path]
    app_identifier: typing.Optional[str]

    def __init__(
        self,
        token: typing.Optional[str] = None,
        private_key: typing.Optional[str] = None,
        private_key_path: typing.Optional[Path] = None,
        app_identifier: typing.Optional[str] = None,
    ):
        env_path_str = os.getenv("GITHUB_PRIVATE_KEY_PATH")
        env_path: typing.Optional[Path] = None
        if env_path_str is not None:
            env_path = Path(env_path_str)

        self.private_key_path = env_path or private_key_path
        self.private_key = None
        if self.private_key_path is not None:
            self.private_key = self.private_key_path.read_text()
        self.private_key = (
            self.private_key or private_key or os.getenv("GITHUB_PRIVATE_KEY")
        )

        self.token = token or os.getenv("GITHUB_TOKEN")
        self.app_identifier = app_identifier or os.getenv("GITHUB_APP_ID")
        assert (self.token is not None) or (
            self.private_key is not None and self.app_identifier is not None
        ), "missing token or secret key and app_identifier. Github's GraphQL endpoint requires authentication."
        # NOTE: We must call `await session.close()` when we are finished with our session.
        # We implement an async context manager this handle this.
        self.session = http.Session()
        self.session.headers[
            "Accept"
        ] = "application/vnd.github.antiope-preview+json,application/vnd.github.merge-info-preview+json"

    async def __aenter__(self) -> "Client":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.session.close()

    def generate_jwt(self) -> str:
        """
        Create an authentication token to make application requests.
        https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-a-github-app

        This is different from authenticating as an installation
        """
        assert (
            self.private_key is not None and self.app_identifier is not None
        ), "we need a private key and app_identifier to generate a JWT"
        issued_at = int(datetime.now().timestamp())
        expiration = int((datetime.now() + timedelta(minutes=10)).timestamp())
        payload = dict(iat=issued_at, exp=expiration, iss=self.app_identifier)
        return jwt.encode(
            payload=payload, key=self.private_key, algorithm="RS256"
        ).decode()

    async def get_token_for_install(self, installation_id: int):
        """
        https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-an-installation
        """
        app_token = self.generate_jwt()
        res = await http.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=dict(
                Accept="application/vnd.github.machine-man-preview+json",
                Authorization=f"Bearer {app_token}",
            ),
        )
        assert res.status_code < 300
        return res.json()["token"]

    async def send_query(
        self,
        query: str,
        variables: typing.Mapping[str, typing.Union[str, int, None]],
        installation_id: typing.Optional[int] = None,
    ) -> GraphQLResponse:
        assert (
            self.entered
        ), "Client must be used in an async context manager. `async with Client() as api: ..."
        log.debug("sending request", query=query, variables=variables)

        if installation_id:
            token = await self.get_token_for_install(installation_id=installation_id)
        else:
            token = self.token or self.generate_jwt()
        self.session.headers["Authorization"] = f"Bearer {token}"
        res = await self.session.post(
            "https://api.github.com/graphql",
            json=(dict(query=query, variables=variables)),
        )
        log.debug("server response", res=res)
        if res.status_code != status.HTTP_200_OK:
            log.warning("server error", res=res)
            raise ServerError(response=res)
        return typing.cast(GraphQLResponse, res.json())

    async def get_default_branch_name(
        self, owner: str, repo: str, installation_id: int
    ) -> str:
        res = await self.send_query(
            query=DEFAULT_BRANCH_NAME_QUERY,
            variables=dict(owner=owner, repo=repo),
            installation_id=installation_id,
        )
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            raise BranchNameError(res=res)
        return typing.cast(str, data["repository"]["defaultBranchRef"]["name"])

    async def get_event_info(
        self,
        owner: str,
        repo: str,
        config_file_expression: str,
        pr_number: int,
        installation_id: int,
    ) -> EventInfoResponse:
        """
        Retrieve all the information we need to evaluate a pull request

        This is basically the "do-all-the-things" query
        """
        res = await self.send_query(
            query=GET_EVENT_INFO_QUERY,
            variables=dict(
                owner=owner,
                repo=repo,
                configFileExpression=config_file_expression,
                PRNumber=pr_number,
            ),
            installation_id=installation_id,
        )

        PAGE_SIZE = 100
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            raise EventInfoError(res=res)

        config: typing.Optional[str] = get_value(
            expr="repository.object.text", data=data
        )

        repo_dict: typing.Dict = get_value(expr="repository", data=data) or {}
        repo_info = RepoInfo(
            merge_commit_allowed=repo_dict.get("mergeCommitAllowed", False),
            rebase_merge_allowed=repo_dict.get("rebaseMergeAllowed", False),
            squash_merge_allowed=repo_dict.get("squashMergeAllowed", False),
        )

        pull_request: typing.Optional[dict] = get_value(
            expr="repository.pullRequest", data=data
        )
        if pull_request is None:
            return EventInfoResponse(config_file=config, pull_request=None, repo=None)

        labels: typing.List[str] = get_values(
            expr="repository.pullRequest.labels.nodes[*].name", data=data
        )
        label_count: typing.Optional[int] = get_value(
            expr="repository.pullRequest.labels.totalCount", data=data
        )
        assert label_count is not None, "we should always be able to get the labels"
        assert label_count <= PAGE_SIZE, "we don't paginate at the moment"
        # update the dictionary to match what we need for parsing
        pull_request["labels"] = labels
        sha: typing.Optional[str] = get_value(
            expr="repository.pullRequest.commits.nodes[0].commit.oid", data=data
        )
        assert sha is not None, "a SHA should always exist"
        pull_request["latest_sha"] = sha
        pr = PullRequest.parse_obj(pull_request)

        return EventInfoResponse(config_file=config, pull_request=pr, repo=repo_info)

    async def merge_pr(
        self,
        pr_id: str,
        sha: str,
        installation_id: int,
        title: typing.Optional[str] = None,
        body: typing.Optional[str] = None,
    ) -> None:
        res = await self.send_query(
            query=MERGE_PR_MUTATION,
            variables=dict(PRId=pr_id, SHA=sha, title=title, body=body),
            installation_id=installation_id,
        )
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None:
            # TODO: Handle error responses from
            raise NotImplementedError()
        log.info("merged_pr", api_response=res)
