from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Union, cast

import arrow
import jwt
import pydantic
import requests_async as http
import structlog
import toml
from asyncio_throttle import Throttler
from mypy_extensions import TypedDict
from pydantic import BaseModel
from starlette import status

import kodiak.app_config as conf
from kodiak.config import V1, MergeMethod
from kodiak.github import events
from kodiak.throttle import get_thottler_for_installation

logger = structlog.get_logger()

CHECK_RUN_NAME = "kodiakhq: status"
APPLICATION_ID = "kodiak"


class ErrorLocation(TypedDict):
    line: int
    column: int


class GraphQLError(TypedDict):
    message: str
    locations: List[ErrorLocation]
    type: Optional[str]
    path: Optional[List[str]]


class GraphQLResponse(TypedDict):
    data: Optional[Dict[Any, Any]]
    errors: Optional[List[GraphQLError]]


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
    assignableUsers(first: 100) {
      nodes {
        login
      }
      totalCount
    }
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
        nodes {
          requestedReviewer {
            __typename
            ... on User {
              login
            }
            ... on Team {
              name
            }
            ... on Mannequin {
              login
            }
          }
        }
      }
      title
      body
      bodyText
      bodyHTML
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
      headRef {
        id
      }
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


class MergeableState(Enum):
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
    number: int
    title: str
    body: str
    bodyText: str
    bodyHTML: str
    mergeStateStatus: MergeStateStatus
    state: PullRequestState
    mergeable: MergeableState
    labels: List[str]
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
    config: Union[V1, pydantic.ValidationError, toml.TomlDecodeError]
    config_str: str
    config_file_expression: str
    pull_request: PullRequest
    repo: RepoInfo
    branch_protection: Optional[BranchProtectionRule]
    review_requests: List[PRReviewRequest]
    head_exists: bool
    reviews: List[PRReview] = field(default_factory=list)
    status_contexts: List[StatusContext] = field(default_factory=list)
    check_runs: List[CheckRun] = field(default_factory=list)
    valid_signature: bool = False
    valid_merge_methods: List[MergeMethod] = field(default_factory=list)


MERGE_PR_MUTATION = """
mutation merge($PRId: ID!, $SHA: GitObjectID!, $title: String, $body: String) {
  mergePullRequest(input: {pullRequestId: $PRId, expectedHeadOid: $SHA, commitHeadline: $title, commitBody: $body}) {
    clientMutationId
  }
}

"""


class BranchProtectionRule(BaseModel):
    requiresApprovingReviews: bool
    requiredApprovingReviewCount: Optional[int]
    requiresStatusChecks: bool
    requiredStatusCheckContexts: List[str]
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


@dataclass
class PRReviewRequest:
    name: str


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
    conclusion: Optional[CheckConclusionState]


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime

    @property
    def expired(self) -> bool:
        return self.expires_at - timedelta(minutes=5) < datetime.now(timezone.utc)


installation_cache: MutableMapping[str, Optional[TokenResponse]] = dict()

# TODO(sbdchd): pass logging via TLS or async equivalent


def get_repo(*, data: dict) -> Optional[dict]:
    try:
        return cast(dict, data["repository"])
    except (KeyError, TypeError):
        return None


def get_config_str(*, repo: dict) -> Optional[str]:
    try:
        return cast(str, repo["object"]["text"])
    except (KeyError, TypeError):
        return None


def get_pull_request(*, repo: dict) -> Optional[dict]:
    try:
        return cast(dict, repo["pullRequest"])
    except (KeyError, TypeError):
        logger.warning("Could not find PR")
        return None


def get_labels(*, pr: dict) -> List[str]:
    try:
        nodes = pr["labels"]["nodes"]
        get_names = (node.get("name") for node in nodes)
        return [label for label in get_names if label is not None]
    except (KeyError, TypeError):
        return []


def get_sha(*, pr: dict) -> Optional[str]:
    try:
        return cast(str, pr["commits"]["nodes"][0]["commit"]["oid"])
    except (IndexError, KeyError, TypeError):
        return None


def get_branch_protection_dicts(*, repo: dict) -> List[dict]:
    try:
        return cast(List[dict], repo["branchProtectionRules"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_branch_protection(
    *, repo: dict, ref_name: str
) -> Optional[BranchProtectionRule]:
    for rule in get_branch_protection_dicts(repo=repo):
        try:
            nodes = rule["matchingRefs"]["nodes"]
        except (KeyError, TypeError):
            nodes = []
        for node in nodes:
            if node["name"] == ref_name:
                try:
                    return BranchProtectionRule.parse_obj(rule)
                except ValueError:
                    logger.warning("Could not parse branch protection")
                    return None
    return None


def get_review_requests_dicts(*, pr: dict) -> List[dict]:
    try:
        return cast(List[dict], pr["reviewRequests"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_requested_reviews(*, pr: dict) -> List[PRReviewRequest]:
    """
    parse from: https://developer.github.com/v4/union/requestedreviewer/
    """
    review_requests: List[PRReviewRequest] = []
    for request_dict in get_review_requests_dicts(pr=pr):
        try:
            request = request_dict["requestedReviewer"]
            typename = request["__typename"]
            if typename in {"User", "Mannequin"}:
                name = request["login"]
            else:
                name = request["name"]
            review_requests.append(PRReviewRequest(name=name))
        except ValueError:
            logger.warning("Could not parse PRReviewRequest")
    return review_requests


def get_review_dicts(*, pr: dict) -> List[dict]:
    try:
        return cast(List[dict], pr["reviews"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_reviews(*, pr: dict) -> List[PRReview]:
    review_dicts = get_review_dicts(pr=pr)
    reviews: List[PRReview] = []
    for review_dict in review_dicts:
        try:
            reviews.append(PRReview.parse_obj(review_dict))
        except ValueError:
            logger.warning("Could not parse PRReview")
    return reviews


def get_status_contexts(*, pr: dict) -> List[StatusContext]:
    try:
        commit_status_dicts: List[dict] = pr["commits"]["nodes"][0]["commit"]["status"][
            "contexts"
        ]
    except (IndexError, KeyError, TypeError):
        commit_status_dicts = []

    status_contexts: List[StatusContext] = []
    for commit_status in commit_status_dicts:
        try:
            status_contexts.append(StatusContext.parse_obj(commit_status))
        except ValueError:
            logger.warning("Could not parse StatusContext")

    return status_contexts


def get_check_runs(*, pr: dict) -> List[CheckRun]:
    check_run_dicts: List[dict] = []
    try:
        for commit_node in pr["commits"]["nodes"]:
            check_suite_nodes = commit_node["commit"]["checkSuites"]["nodes"]
            for check_run_node in check_suite_nodes:
                check_run_nodes = check_run_node["checkRuns"]["nodes"]
                for check_run in check_run_nodes:
                    check_run_dicts.append(check_run)
    except (KeyError, TypeError):
        pass

    check_runs: List[CheckRun] = []
    for check_run_dict in check_run_dicts:
        try:
            check_runs.append(CheckRun.parse_obj(check_run_dict))
        except ValueError:
            logger.warning("Could not parse CheckRun")
    return check_runs


def get_valid_signature(*, pr: dict) -> bool:
    try:
        return bool(pr["commits"]["nodes"][0]["commit"]["signature"]["isValid"])
    except (IndexError, KeyError, TypeError):
        return False


def get_head_exists(*, pr: dict) -> bool:
    try:
        return bool(pr["headRef"]["id"])
    except (KeyError, TypeError):
        return False


def get_valid_merge_methods(*, repo: dict) -> List[MergeMethod]:
    valid_merge_methods: List[MergeMethod] = []
    if repo.get("mergeCommitAllowed"):
        valid_merge_methods.append(MergeMethod.merge)

    if repo.get("rebaseMergeAllowed"):
        valid_merge_methods.append(MergeMethod.rebase)

    if repo.get("squashMergeAllowed"):
        valid_merge_methods.append(MergeMethod.squash)
    return valid_merge_methods


class Client:
    session: http.Session
    throttler: Throttler

    def __init__(self, *, owner: str, repo: str, installation_id: str):

        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        # NOTE: We must call `await session.close()` when we are finished with our session.
        # We implement an async context manager this handle this.
        self.session = http.Session()
        self.session.headers[
            "Accept"
        ] = "application/vnd.github.antiope-preview+json,application/vnd.github.merge-info-preview+json"

    async def __aenter__(self) -> Client:
        self.throttler = await get_thottler_for_installation(
            installation_id=self.installation_id
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.session.close()

    async def send_query(
        self,
        query: str,
        variables: Mapping[str, Union[str, int, None]],
        installation_id: str,
        remaining_retries: int = 4,
    ) -> Optional[GraphQLResponse]:
        log = logger.bind(install=installation_id)

        token = await get_token_for_install(installation_id=installation_id)
        self.session.headers["Authorization"] = f"Bearer {token}"
        async with self.throttler:
            res = await self.session.post(
                "https://api.github.com/graphql",
                json=(dict(query=query, variables=variables)),
            )
        rate_limit_remaining = res.headers.get("x-ratelimit-remaining")
        rate_limit_max = res.headers.get("x-ratelimit-limit")
        rate_limit = f"{rate_limit_remaining}/{rate_limit_max}"
        log = log.bind(rate_limit=rate_limit)
        if res.status_code != status.HTTP_200_OK:
            log.error("github api request error", res=res)
            return None
        return cast(GraphQLResponse, res.json())

    async def get_default_branch_name(self) -> Optional[str]:
        res = await self.send_query(
            query=DEFAULT_BRANCH_NAME_QUERY,
            variables=dict(owner=self.owner, repo=self.repo),
            installation_id=self.installation_id,
        )
        if res is None:
            return None
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            logger.error("could not fetch default branch name", res=res)
            return None
        return cast(str, data["repository"]["defaultBranchRef"]["name"])

    async def get_event_info(
        self, config_file_expression: str, pr_number: int
    ) -> Optional[EventInfoResponse]:
        """
        Retrieve all the information we need to evaluate a pull request

        This is basically the "do-all-the-things" query
        """
        log = logger.bind(
            repo=f"{self.owner}/{self.repo}", pr=pr_number, install=self.installation_id
        )
        res = await self.send_query(
            query=GET_EVENT_INFO_QUERY,
            variables=dict(
                owner=self.owner,
                repo=self.repo,
                configFileExpression=config_file_expression,
                PRNumber=pr_number,
            ),
            installation_id=self.installation_id,
        )
        if res is None:
            return None

        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            log.error("could not fetch event info", res=res)
            return None

        repository = get_repo(data=data)
        if not repository:
            log.warning("could not find repository")
            return None

        config_str = get_config_str(repo=repository)
        if config_str is None:
            # NOTE(chdsbd): we don't want to show a message for this as the lack
            # of a config allows kodiak to be selectively installed
            log.warning("could not find configuration file")
            return None

        pull_request = get_pull_request(repo=repository)
        if not pull_request:
            log.warning("Could not find PR")
            return None

        config = V1.parse_toml(config_str)

        # update the dictionary to match what we need for parsing
        pull_request["labels"] = get_labels(pr=pull_request)
        pull_request["latest_sha"] = get_sha(pr=pull_request)
        pull_request["number"] = pr_number
        try:
            pr = PullRequest.parse_obj(pull_request)
        except ValueError:
            log.warning("Could not parse pull request")
            return None

        branch_protection = get_branch_protection(
            repo=repository, ref_name=pr.baseRefName
        )

        return EventInfoResponse(
            config=config,
            config_str=config_str,
            config_file_expression=config_file_expression,
            pull_request=pr,
            repo=RepoInfo(
                merge_commit_allowed=repository.get("mergeCommitAllowed", False),
                rebase_merge_allowed=repository.get("rebaseMergeAllowed", False),
                squash_merge_allowed=repository.get("squashMergeAllowed", False),
            ),
            branch_protection=branch_protection,
            review_requests=get_requested_reviews(pr=pull_request),
            reviews=get_reviews(pr=pull_request),
            status_contexts=get_status_contexts(pr=pull_request),
            check_runs=get_check_runs(pr=pull_request),
            head_exists=get_head_exists(pr=pull_request),
            valid_signature=get_valid_signature(pr=pull_request),
            valid_merge_methods=get_valid_merge_methods(repo=repository),
        )

    async def get_pull_requests_for_sha(
        self, sha: str
    ) -> Optional[List[events.BasePullRequest]]:
        log = logger.bind(
            repo=f"{self.owner}/{self.repo}", install=self.installation_id, sha=sha
        )
        headers = await get_headers(installation_id=self.installation_id)
        async with self.throttler:
            res = await self.session.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?state=open&sort=updated&head={sha}",
                headers=headers,
            )
        if res.status_code != 200:
            log.error("problem finding prs", res=res, res_json=res.json())
            return None
        return [events.BasePullRequest.parse_obj(pr) for pr in res.json()]

    async def delete_branch(self, branch: str) -> bool:
        """
        delete a branch by name
        """
        log = logger.bind(
            repo=f"{self.owner}/{self.repo}",
            install=self.installation_id,
            branch=branch,
        )
        headers = await get_headers(installation_id=self.installation_id)
        ref = f"heads/{branch}"
        async with self.throttler:
            res = await self.session.delete(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/git/refs/{ref}",
                headers=headers,
            )
        if res.status_code != 204:
            log.error("problem deleting branch", res=res, res_json=res.json())
            return False
        return True

    async def merge_branch(self, head: str, base: str) -> http.Response:
        headers = await get_headers(installation_id=self.installation_id)
        async with self.throttler:
            return await self.session.post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/merges",
                json=dict(head=head, base=base),
                headers=headers,
            )

    async def get_pull_request(self, number: int) -> Optional[dict]:
        headers = await get_headers(installation_id=self.installation_id)
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{number}"
        async with self.throttler:
            res = await self.session.get(url, headers=headers)
        if not res.ok:
            return None
        return cast(dict, res.json())

    async def merge_pull_request(self, number: int, body: dict) -> http.Response:
        headers = await get_headers(installation_id=self.installation_id)
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{number}/merge"
        async with self.throttler:
            return await self.session.put(url, headers=headers, json=body)

    async def create_notification(
        self, head_sha: str, message: str, summary: Optional[str] = None
    ) -> http.Response:
        headers = await get_headers(installation_id=self.installation_id)
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/check-runs"
        body = dict(
            name=CHECK_RUN_NAME,
            head_sha=head_sha,
            status="completed",
            completed_at=arrow.utcnow().isoformat(),
            conclusion="neutral",
            output=dict(title=message, summary=summary or ""),
        )
        async with self.throttler:
            return await self.session.post(url, headers=headers, json=body)


def generate_jwt(*, private_key: str, app_identifier: str) -> str:
    """
    Create an authentication token to make application requests.
    https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-a-github-app

    This is different from authenticating as an installation
    """
    issued_at = int(datetime.now().timestamp())
    expiration = int((datetime.now() + timedelta(minutes=10)).timestamp())
    payload = dict(iat=issued_at, exp=expiration, iss=app_identifier)
    return jwt.encode(payload=payload, key=private_key, algorithm="RS256").decode()


async def get_token_for_install(*, installation_id: str) -> str:
    """
    https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-an-installation
    """
    token = installation_cache.get(installation_id)
    if token is not None and not token.expired:
        return token.token
    app_token = generate_jwt(
        private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID
    )
    throttler = await get_thottler_for_installation(
        # this isn't a real installation ID, but it provides rate limiting
        # for our GithubApp instead of the installations we typically act as
        installation_id=APPLICATION_ID
    )
    async with throttler:
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


async def get_headers(*, installation_id: str) -> Mapping[str, str]:
    token = await get_token_for_install(installation_id=installation_id)
    return dict(
        Authorization=f"token {token}",
        Accept="application/vnd.github.machine-man-preview+json,application/vnd.github.antiope-preview+json",
    )
