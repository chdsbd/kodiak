from __future__ import annotations

import os
import typing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import jwt
import requests_async as http
import structlog
from jsonpath_rw import parse
from mypy_extensions import TypedDict
from pydantic import BaseModel
from requests_async import Response
from starlette import status

from kodiak.config import V1, MergeMethod
from kodiak.github import events

logger = structlog.get_logger()


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


GET_EVENT_INFO_QUERY = """
query GetEventInfo($owner: String!, $repo: String!, $configFileExpression: String!, $PRNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    branchProtectionRules(first: 100) {
      nodes {
        matchingRefs(first: 100) {
          nodes {
            name
          }
        }
        requiresApprovingReviews
        requiredApprovingReviewCount
        requiresStatusChecks
        requiredStatusCheckContexts
        requiresStrictStatusChecks
        requiresCommitSignatures
      }
    }
    mergeCommitAllowed
    rebaseMergeAllowed
    squashMergeAllowed
    pullRequest(number: $PRNumber) {
      id
      mergeStateStatus
      state
      mergeable
      reviewRequests(first: 100) {
        totalCount
      }
      reviews(first: 100) {
        nodes {
          createdAt
          state
          author {
            login
          }
          authorAssociation
        }
        totalCount
      }
      baseRefName
      headRefName
      commits(last: 1) {
        nodes {
          commit {
            checkSuites(first: 100) {
              nodes {
                checkRuns(first: 100) {
                  nodes {
                    name
                    conclusion
                  }
                }
              }
            }
            oid
            signature {
              isValid
            }
            status {
              state
              contexts {
                context
                state
              }
            }
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


class MergableState(Enum):
    # The pull request cannot be merged due to merge conflicts.
    CONFLICTING = "CONFLICTING"
    # The pull request can be merged.
    MERGEABLE = "MERGEABLE"
    # The mergeability of the pull request is still being calculated.
    UNKNOWN = "UNKNOWN"


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
    mergeable: MergableState
    labels: typing.List[str]
    # the SHA of the most recent commit
    latest_sha: str
    baseRefName: str
    headRefName: str


@dataclass
class RepoInfo:
    merge_commit_allowed: bool
    rebase_merge_allowed: bool
    squash_merge_allowed: bool


@dataclass
class EventInfoResponse:
    config: V1
    pull_request: PullRequest
    repo: RepoInfo
    branch_protection: BranchProtectionRule
    review_requests_count: int
    reviews: typing.List[PRReview] = field(default_factory=list)
    status_contexts: typing.List[StatusContext] = field(default_factory=list)
    check_runs: typing.List[CheckRun] = field(default_factory=list)
    valid_signature: bool = False
    valid_merge_methods: typing.List[MergeMethod] = field(default_factory=list)


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


class BranchProtectionRule(BaseModel):
    requiresApprovingReviews: bool
    requiredApprovingReviewCount: typing.Optional[int]
    requiresStatusChecks: bool
    requiredStatusCheckContexts: typing.List[str]
    requiresStrictStatusChecks: bool
    requiresCommitSignatures: bool


class PRReviewState(Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class CommentAuthorAssociation(Enum):
    COLLABORATOR = "COLLABORATOR"
    CONTRIBUTOR = "CONTRIBUTOR"
    FIRST_TIMER = "FIRST_TIMER"
    FIRST_TIME_CONTRIBUTOR = "FIRST_TIME_CONTRIBUTOR"
    MEMBER = "MEMBER"
    NONE = "NONE"
    OWNER = "OWNER"


class PRReviewAuthor(BaseModel):
    login: str


class PRReview(BaseModel):
    state: PRReviewState
    createdAt: datetime
    author: PRReviewAuthor
    authorAssociation: CommentAuthorAssociation


class StatusState(Enum):
    ERROR = "ERROR"
    EXPECTED = "EXPECTED"
    FAILURE = "FAILURE"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"


class StatusContext(BaseModel):
    context: str
    state: StatusState


class CheckConclusionState(Enum):
    ACTION_REQUIRED = "ACTION_REQUIRED"
    CANCELLED = "CANCELLED"
    FAILURE = "FAILURE"
    NEUTRAL = "NEUTRAL"
    SUCCESS = "SUCCESS"
    TIMED_OUT = "TIMED_OUT"


class CheckRun(BaseModel):
    name: str
    conclusion: typing.Optional[CheckConclusionState]


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime

    @property
    def expired(self) -> bool:
        return self.expires_at - timedelta(minutes=5) < datetime.now(timezone.utc)


installation_cache: typing.MutableMapping[str, typing.Optional[TokenResponse]] = dict()


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

    async def __aexit__(
        self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any
    ) -> None:
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

    async def get_token_for_install(self, installation_id: str) -> str:
        """
        https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-an-installation
        """
        token = installation_cache.get(installation_id)
        if token is not None and not token.expired:
            return token.token
        app_token = self.generate_jwt()
        res = await http.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=dict(
                Accept="application/vnd.github.machine-man-preview+json",
                Authorization=f"Bearer {app_token}",
            ),
        )
        assert res.status_code < 300
        token_response = TokenResponse(**res.json())
        installation_cache[installation_id] = token_response
        return token_response.token

    async def send_query(
        self,
        query: str,
        variables: typing.Mapping[str, typing.Union[str, int, None]],
        installation_id: typing.Optional[str] = None,
        remaining_retries: int = 4,
    ) -> typing.Optional[GraphQLResponse]:
        log = logger.bind(install=installation_id)
        assert (
            self.entered
        ), "Client must be used in an async context manager. `async with Client() as api: ..."

        if installation_id:
            token = await self.get_token_for_install(installation_id=installation_id)
        else:
            token = self.token or self.generate_jwt()
        self.session.headers["Authorization"] = f"Bearer {token}"
        log.info("sending query")
        res = await self.session.post(
            "https://api.github.com/graphql",
            json=(dict(query=query, variables=variables)),
        )
        if res.status_code != status.HTTP_200_OK:
            log.error("github api request error", res=res)
            return None
        return typing.cast(GraphQLResponse, res.json())

    async def get_default_branch_name(
        self, owner: str, repo: str, installation_id: str
    ) -> typing.Optional[str]:
        res = await self.send_query(
            query=DEFAULT_BRANCH_NAME_QUERY,
            variables=dict(owner=owner, repo=repo),
            installation_id=installation_id,
        )
        if res is None:
            return None
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            logger.error("could not fetch default branch name", res=res)
            return None
        return typing.cast(str, data["repository"]["defaultBranchRef"]["name"])

    async def get_event_info(
        self,
        owner: str,
        repo: str,
        config_file_expression: str,
        pr_number: int,
        installation_id: str,
    ) -> typing.Optional[EventInfoResponse]:
        """
        Retrieve all the information we need to evaluate a pull request

        This is basically the "do-all-the-things" query
        """
        log = logger.bind(repo=f"{owner}/{repo}", pr=pr_number, install=installation_id)
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
        if res is None:
            return None

        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            log.error("could not fetch event info", res=res)
            return None

        config_str: typing.Optional[str] = get_value(
            expr="repository.object.text", data=data
        )

        if config_str is None:
            log.warning("could not find configuration file")
            return None

        try:
            config = V1.parse_toml(config_str)
        except ValueError:
            log.warning("could not parse configuration")
            return None

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
            log.warning("Could not find PR")
            return None

        labels: typing.List[str] = get_values(
            expr="repository.pullRequest.labels.nodes[*].name", data=data
        )

        # update the dictionary to match what we need for parsing
        pull_request["labels"] = labels
        sha: typing.Optional[str] = get_value(
            expr="repository.pullRequest.commits.nodes[0].commit.oid", data=data
        )

        pull_request["latest_sha"] = sha
        try:
            pr = PullRequest.parse_obj(pull_request)
        except ValueError:
            log.warning("Could not parse pull request")
            return None

        branch_protection_dicts: typing.List[dict] = get_values(
            expr="repository.branchProtectionRules.nodes[*]", data=data
        )

        def find_branch_protection(
            response_data: typing.List[dict], ref_name: str
        ) -> typing.Optional[BranchProtectionRule]:
            for rule in branch_protection_dicts:
                for node in rule.get("matchingRefs", {}).get("nodes", []):
                    if node["name"] == ref_name:
                        try:
                            return BranchProtectionRule.parse_obj(rule)
                        except ValueError:
                            log.warning("Could not parse branch protection")
                            return None
            return None

        branch_protection = find_branch_protection(
            branch_protection_dicts, pr.baseRefName
        )
        if branch_protection is None:
            log.warning("Could not find branch protection")
            return None

        review_requests_count: int = get_value(
            expr="repository.pullRequest.reviewRequests.totalCount", data=data
        ) or 0

        review_dicts: typing.List[dict] = get_values(
            expr="repository.pullRequest.reviews.nodes[*]", data=data
        )
        reviews: typing.List[PRReview] = []
        for review_dict in review_dicts:
            try:
                reviews.append(PRReview.parse_obj(review_dict))
            except ValueError:
                log.warning("Could not parse PRReview")

        commit_status_dicts: typing.List[dict] = get_values(
            expr="repository.pullRequest.commits.nodes[0].commit.status.contexts[*]",
            data=data,
        )

        status_contexts: typing.List[StatusContext] = []
        for commit_status in commit_status_dicts:
            try:
                status_contexts.append(StatusContext.parse_obj(commit_status))
            except ValueError:
                log.warning("Could not parse StatusContext")

        check_run_dicts: typing.List[dict] = get_values(
            expr="repository.pullRequest.commits.nodes[*].commit.checkSuites.nodes[*].checkRuns.nodes[*]",
            data=data,
        )
        check_runs: typing.List[CheckRun] = []
        for check_run_dict in check_run_dicts:
            try:
                check_runs.append(CheckRun.parse_obj(check_run_dict))
            except ValueError:
                log.warning("Could not parse CheckRun")

        valid_signature = (
            get_value(
                expr="repository.pullRequest.commits.nodes[0].commit.signature.isValid",
                data=data,
            )
            or False
        )

        valid_merge_methods: typing.List[MergeMethod] = []
        if get_value(expr="repository.mergeCommitAllowed", data=data):
            valid_merge_methods.append(MergeMethod.merge)
        if get_value(expr="repository.rebaseMergeAllowed", data=data):
            valid_merge_methods.append(MergeMethod.rebase)
        if get_value(expr="repository.squashMergeAllowed", data=data):
            valid_merge_methods.append(MergeMethod.squash)

        return EventInfoResponse(
            config=config,
            pull_request=pr,
            repo=repo_info,
            branch_protection=branch_protection,
            review_requests_count=review_requests_count,
            reviews=reviews,
            status_contexts=status_contexts,
            check_runs=check_runs,
            valid_signature=valid_signature,
            valid_merge_methods=valid_merge_methods,
        )

    async def get_pull_requests_for_sha(
        self, owner: str, repo: str, installation_id: str, sha: str
    ) -> typing.Optional[typing.List[events.BasePullRequest]]:
        log = logger.bind(repo=f"{owner}/{repo}", install=installation_id, sha=sha)
        async with Client() as client:
            token = await client.get_token_for_install(installation_id=installation_id)
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )
            res = await client.session.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&sort=updated&head={sha}",
                headers=headers,
            )
            if res.status_code != 200:
                log.error("problem finding prs", res=res, res_json=res.json())
                return None
            return [events.BasePullRequest.parse_obj(pr) for pr in res.json()]
