from __future__ import annotations

import asyncio
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
query ($owner: String!, $repo: String!, $PRNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef {
      name
    }
    pullRequest(number: $PRNumber) {
      baseRefName
    }
  }
}
"""


GET_EVENT_INFO_QUERY = """
query GetEventInfo(
    $owner: String!,
    $repo: String!,
    $PRNumber: Int!,
    $ownersGithubFileExpression: String!,
    $ownersDocsFileExpression: String!,
    $ownersRootFileExpression: String!,
    $configFileExpression: String!
  ) {
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
        requiresCodeOwnerReviews
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
      isCrossRepository
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
    owners_root_file: object(expression: $ownersRootFileExpression) {
      ... on Blob {
        text
      }
    }
    owners_docs_file: object(expression: $ownersDocsFileExpression) {
      ... on Blob {
        text
      }
    }
    owners_github_file: object(expression: $ownersGithubFileExpression) {
      ... on Blob {
        text
      }
    }
    config_file: object(expression: $configFileExpression) {
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
    isCrossRepository: bool
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
    owners_str: Optional[str]
    pull_request: PullRequest
    repo: RepoInfo
    branch_protection: Optional[BranchProtectionRule]
    review_requests: List[PRReviewRequest]
    head_exists: bool
    file_paths: List[str] = field(default_factory=list)
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
    requiresCodeOwnerReviews: bool


class PRReviewState(Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class PRReviewAuthorSchema(BaseModel):
    login: str


@dataclass
class PRReviewAuthor:
    login: str
    permission: Permission


class PRReviewSchema(BaseModel):
    state: PRReviewState
    createdAt: datetime
    author: PRReviewAuthorSchema


@dataclass
class PRReview:
    state: PRReviewState
    createdAt: datetime
    author: PRReviewAuthor


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


class Permission(Enum):
    """
    https://developer.github.com/v3/repos/collaborators/#review-a-users-permission-level
    """

    ADMIN = "admin"
    WRITE = "write"
    READ = "read"
    NONE = "none"


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
        return cast(str, repo["config_file"]["text"])
    except (KeyError, TypeError):
        return None


def get_owners_str(*, repo: dict) -> Optional[str]:
    for owner_kind in ("owners_root_file", "owners_github_file", "owners_docs_file"):
        try:
            return cast(str, repo[owner_kind]["text"])
        except (KeyError, TypeError):
            continue
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


def get_reviews(*, pr: dict) -> List[PRReviewSchema]:
    review_dicts = get_review_dicts(pr=pr)
    reviews: List[PRReviewSchema] = []
    for review_dict in review_dicts:
        try:
            reviews.append(PRReviewSchema.parse_obj(review_dict))
        except ValueError:
            logger.warning("Could not parse PRReviewSchema")
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


@dataclass
class BranchInfo:
    default_branch_name: Optional[str]
    base_ref_name: Optional[str]


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

    async def get_default_branch_name(self, *, pr_number: int) -> Optional[BranchInfo]:
        res = await self.send_query(
            query=DEFAULT_BRANCH_NAME_QUERY,
            variables=dict(owner=self.owner, repo=self.repo, PRNumber=pr_number),
            installation_id=self.installation_id,
        )
        if res is None:
            return None
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            logger.error("could not fetch default branch name", res=res)
            return None
        try:
            base_ref_name: Optional[str] = cast(
                str, data["repository"]["pullRequest"]["baseRefName"]
            )
        except (IndexError, ValueError, TypeError):
            base_ref_name = None
        try:
            default_branch_name: Optional[str] = cast(
                str, data["repository"]["defaultBranchRef"]["name"]
            )
        except (IndexError, ValueError, TypeError):
            default_branch_name = None

        return BranchInfo(
            default_branch_name=default_branch_name, base_ref_name=base_ref_name
        )

    async def get_files_for_pr(self, pr_number: int, page_limit: int = 3) -> List[str]:
        """
        Use the GitHub v3 api to fetch file names affected by a PR

        We set a limit on the number of pages we ask for as some PRs can touch
        thousands of files and it would take a relatively long time to fetch
        them.

        Since we must limit the api requests we make we must accept some
        inaccuracies. We can miss files that would help identify a code owner.
        In this case, Kodiak will likely update the branch as it cannot
        calculate that it should be blocked. It will then encounter an unknown
        blockage. This update/block cycle could repeat, but there's nothing
        obvious we can do to fix this.

        We might be able to do something with fetching the repository and doing
        something locally, but I'm not sure how that would compare to HTTP
        requests.
        """
        headers = await get_headers(installation_id=self.installation_id)
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files?page_size=300"
        file_paths: List[str] = []
        while page_limit:
            page_limit -= 1
            async with self.throttler:
                res = await self.session.get(url, headers=headers)
                for file in res.json():
                    file_paths.append(file["filename"])
            if "url" in res.links.get("next", []):
                url = res.links["next"]["url"]
            else:
                break
        return file_paths

    async def get_permissions_for_username(self, username: str) -> Permission:
        headers = await get_headers(installation_id=self.installation_id)
        async with self.throttler:
            res = await self.session.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/collaborators/{username}/permission",
                headers=headers,
            )
        try:
            res.raise_for_status()
            return Permission(res.json()["permission"])
        except (http.HTTPError, IndexError, TypeError, ValueError):
            logger.exception("couldn't fetch permissions for username %r", username)
            return Permission.NONE

    # TODO(chdsbd): We may want to cache this response to improve performance as
    # we could encounter a lot of throttling when hitting the Github API
    async def get_reviewers_and_permissions(
        self, *, reviews: List[PRReviewSchema]
    ) -> List[PRReview]:
        reviewer_names = {review.author.login for review in reviews}

        requests = [
            self.get_permissions_for_username(username) for username in reviewer_names
        ]
        permissions = await asyncio.gather(*requests)

        user_permission_mapping = {
            username: permission
            for username, permission in zip(reviewer_names, permissions)
        }

        return [
            PRReview(
                state=review.state,
                createdAt=review.createdAt,
                author=PRReviewAuthor(
                    login=review.author.login,
                    permission=user_permission_mapping[review.author.login],
                ),
            )
            for review in reviews
        ]

    async def get_event_info(
        self,
        *,
        pr_number: int,
        owners_root_file_expression: str,
        owners_github_file_expression: str,
        owners_docs_file_expression: str,
        config_file_expression: str,
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
                ownersRootFileExpression=owners_root_file_expression,
                ownersDocsFileExpression=owners_docs_file_expression,
                ownersGithubFileExpression=owners_github_file_expression,
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

        owners_str = get_owners_str(repo=repository)

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

        partial_reviews = get_reviews(pr=pull_request)
        reviews_with_permissions = await self.get_reviewers_and_permissions(
            reviews=partial_reviews
        )

        if branch_protection and branch_protection.requiresCodeOwnerReviews:
            file_paths = await self.get_files_for_pr(pr.number)
        else:
            file_paths = []
        return EventInfoResponse(
            config=config,
            config_str=config_str,
            config_file_expression=config_file_expression,
            owners_str=owners_str,
            pull_request=pr,
            repo=RepoInfo(
                merge_commit_allowed=repository.get("mergeCommitAllowed", False),
                rebase_merge_allowed=repository.get("rebaseMergeAllowed", False),
                squash_merge_allowed=repository.get("squashMergeAllowed", False),
            ),
            branch_protection=branch_protection,
            file_paths=file_paths,
            review_requests=get_requested_reviews(pr=pull_request),
            reviews=reviews_with_permissions,
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
