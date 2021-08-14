from __future__ import annotations

import asyncio
import urllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Set, Union, cast

import httpx as http
import jwt
import pydantic
import structlog
import toml
from mypy_extensions import TypedDict
from pydantic import BaseModel
from typing_extensions import Literal, Protocol

import kodiak.app_config as conf
from kodiak.config import V1, MergeMethod
from kodiak.queries.commits import Commit, CommitConnection, GitActor
from kodiak.queries.commits import User as PullRequestCommitUser
from kodiak.queries.commits import get_commits
from kodiak.throttle import get_thottler_for_installation

logger = structlog.get_logger()

CHECK_RUN_NAME = "kodiakhq: status"
APPLICATION_ID = "kodiak"
CONFIG_FILE_NAME = ".kodiak.toml"


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


GET_CONFIG_QUERY = """
query ($owner: String!, $repo: String!, $rootConfigFileExpression: String!, $githubConfigFileExpression: String!) {
  repository(owner: $owner, name: $repo) {
    rootConfigFile: object(expression: $rootConfigFileExpression) {
      ... on Blob {
        text
      }
    }
    githubConfigFile: object(expression: $githubConfigFileExpression) {
      ... on Blob {
        text
      }
    }
  }
}
"""


class ConfigQueryText(pydantic.BaseModel):
    text: Optional[str]


class ConfigQueryOptions(pydantic.BaseModel):
    rootConfigFile: Optional[ConfigQueryText]
    githubConfigFile: Optional[ConfigQueryText]


class ConfigQueryResponse(pydantic.BaseModel):
    repository: Optional[ConfigQueryOptions]


GET_EVENT_INFO_QUERY = """
query GetEventInfo($owner: String!, $repo: String!, $PRNumber: Int!) {
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
        requiresCodeOwnerReviews
        requiresCommitSignatures
        requiresConversationResolution
        restrictsPushes
        pushAllowances(first: 100) {
          nodes {
            actor {
              ... on App {
                databaseId
              }
            }
          }
        }
      }
    }
    mergeCommitAllowed
    rebaseMergeAllowed
    squashMergeAllowed
    deleteBranchOnMerge
    isPrivate
    pullRequest(number: $PRNumber) {
      id
      author {
        login
        type: __typename
        ... on User {
          databaseId
          name
        }
        ... on Bot {
          databaseId
        }
      }
      isDraft
      mergeStateStatus
      reviewDecision
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
      reviewThreads(first: 100) {
        nodes {
          isCollapsed
        }
      }
      title
      body
      bodyText
      bodyHTML
      url
      reviews(first: 100) {
        nodes {
          createdAt
          state
          author {
            login
            type: __typename
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
      commitHistory: commits(last: 100) {
        nodes {
          commit {
            author {
              user {
                databaseId
                name
                login
                type: __typename
              }
            }
            parents {
              totalCount
            }
          }
        }
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
    #
    # this member is being removed 2021-01-01. PullRequest.isDraft should be used instead.
    # https://docs.github.com/en/free-pro-team@latest/graphql/overview/breaking-changes#changes-scheduled-for-2021-01-01
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


class PullRequestAuthor(BaseModel):
    login: str
    databaseId: int
    type: str
    name: Optional[str] = None


class PullRequestReviewDecision(Enum):
    # The pull request has received an approving review.
    APPROVED = "APPROVED"
    # Changes have been requested on the pull request.
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    # A review is required before the pull request can be merged.
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReviewThread(BaseModel):
    isCollapsed: bool


class ReviewThreadConnection(BaseModel):
    nodes: Optional[List[ReviewThread]]


class PullRequest(BaseModel):
    id: str
    number: int
    title: str
    body: str
    bodyText: str
    bodyHTML: str
    author: PullRequestAuthor
    isDraft: bool
    mergeStateStatus: MergeStateStatus
    # null if the pull request does not require a review by default (no branch
    # protection), and no review was requested or submitted yet.
    reviewDecision: Optional[PullRequestReviewDecision]
    reviewThreads: ReviewThreadConnection
    state: PullRequestState
    mergeable: MergeableState
    isCrossRepository: bool
    labels: List[str]
    # the SHA of the most recent commit
    latest_sha: str
    baseRefName: str
    headRefName: str
    url: str


class RepoInfo(BaseModel):
    merge_commit_allowed: bool
    rebase_merge_allowed: bool
    squash_merge_allowed: bool
    delete_branch_on_merge: bool
    is_private: bool


@dataclass
class EventInfoResponse:
    config: Union[V1, pydantic.ValidationError, toml.TomlDecodeError]
    config_str: str
    config_file_expression: str
    pull_request: PullRequest
    repository: RepoInfo
    subscription: Optional[Subscription]
    branch_protection: Optional[BranchProtectionRule]
    review_requests: List[PRReviewRequest]
    head_exists: bool
    reviews: List[PRReview] = field(default_factory=list)
    status_contexts: List[StatusContext] = field(default_factory=list)
    check_runs: List[CheckRun] = field(default_factory=list)
    valid_merge_methods: List[MergeMethod] = field(default_factory=list)
    commits: List[Commit] = field(default_factory=list)


MERGE_PR_MUTATION = """
mutation merge($PRId: ID!, $SHA: GitObjectID!, $title: String, $body: String) {
  mergePullRequest(input: {pullRequestId: $PRId, expectedHeadOid: $SHA, commitHeadline: $title, commitBody: $body}) {
    clientMutationId
  }
}

"""


class PushAllowanceActor(BaseModel):
    """
    https://developer.github.com/v4/object/app/
    """

    # databaseId will be None for non github apps (users, organizations, teams).
    databaseId: Optional[int]


class PushAllowance(BaseModel):
    """
    https://developer.github.com/v4/object/pushallowance/
    """

    actor: PushAllowanceActor


class NodeListPushAllowance(BaseModel):
    nodes: List[PushAllowance]


class BranchProtectionRule(BaseModel):
    """
    https://developer.github.com/v4/object/branchprotectionrule/
    """

    requiresApprovingReviews: bool
    requiredApprovingReviewCount: Optional[int]
    requiresStatusChecks: bool
    requiredStatusCheckContexts: List[str]
    requiresStrictStatusChecks: bool
    requiresCodeOwnerReviews: bool
    requiresCommitSignatures: bool
    requiresConversationResolution: bool
    restrictsPushes: bool
    pushAllowances: NodeListPushAllowance


class PRReviewState(Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class Actor(Enum):
    """
    https://developer.github.com/v4/interface/actor/
    """

    Bot = "Bot"
    EnterpriseUserAccount = "EnterpriseUserAccount"
    Mannequin = "Mannequin"
    Organization = "Organization"
    User = "User"


class PRReviewAuthorSchema(BaseModel):
    login: str
    type: Actor


@dataclass
class PRReviewAuthor:
    login: str
    permission: Permission


class PRReviewSchema(BaseModel):
    state: PRReviewState
    createdAt: datetime
    author: Optional[PRReviewAuthorSchema]


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
    SKIPPED = "SKIPPED"
    STALE = "STALE"
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


def get_repo(*, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return cast(Dict[str, Any], data["repository"])
    except (KeyError, TypeError):
        return None


def get_root_config_str(*, repo: Dict[str, Any]) -> Optional[str]:
    try:
        return cast(str, repo["rootConfigFile"]["text"])
    except (KeyError, TypeError):
        return None


def get_github_config_str(*, repo: Dict[str, Any]) -> Optional[str]:
    try:
        return cast(str, repo["githubConfigFile"]["text"])
    except (KeyError, TypeError):
        return None


def get_pull_request(*, repo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return cast(Dict[str, Any], repo["pullRequest"])
    except (KeyError, TypeError):
        logger.warning("Could not find PR", exc_info=True)
        return None


def get_labels(*, pr: Dict[str, Any]) -> List[str]:
    try:
        nodes = pr["labels"]["nodes"]
        get_names = (node.get("name") for node in nodes)
        return [label for label in get_names if label is not None]
    except (KeyError, TypeError):
        return []


def get_sha(*, pr: Dict[str, Any]) -> Optional[str]:
    try:
        return cast(str, pr["commits"]["nodes"][0]["commit"]["oid"])
    except (IndexError, KeyError, TypeError):
        return None


def get_branch_protection_dicts(*, repo: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return cast(List[Dict[str, Any]], repo["branchProtectionRules"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_branch_protection(
    *, repo: Dict[str, Any], ref_name: str
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
                    logger.warning("Could not parse branch protection", exc_info=True)
                    return None
    return None


def get_review_requests_dicts(*, pr: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return cast(List[Dict[str, Any]], pr["reviewRequests"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_requested_reviews(*, pr: Dict[str, Any]) -> List[PRReviewRequest]:
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
            logger.warning("Could not parse PRReviewRequest", exc_info=True)
    return review_requests


def get_review_dicts(*, pr: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        return cast(List[Dict[str, Any]], pr["reviews"]["nodes"])
    except (KeyError, TypeError):
        return []


def get_reviews(*, pr: Dict[str, Any]) -> List[PRReviewSchema]:
    review_dicts = get_review_dicts(pr=pr)
    reviews: List[PRReviewSchema] = []
    for review_dict in review_dicts:
        try:
            reviews.append(PRReviewSchema.parse_obj(review_dict))
        except ValueError:
            logger.warning("Could not parse PRReviewSchema", exc_info=True)
    return reviews


def get_status_contexts(*, pr: Dict[str, Any]) -> List[StatusContext]:
    try:
        commit_status_dicts: List[Dict[str, Any]] = pr["commits"]["nodes"][0]["commit"][
            "status"
        ]["contexts"]
    except (IndexError, KeyError, TypeError):
        commit_status_dicts = []

    status_contexts: List[StatusContext] = []
    for commit_status in commit_status_dicts:
        try:
            status_contexts.append(StatusContext.parse_obj(commit_status))
        except ValueError:
            logger.warning("Could not parse StatusContext", exc_info=True)

    return status_contexts


def get_check_runs(*, pr: Dict[str, Any]) -> List[CheckRun]:
    check_run_dicts: List[Dict[str, Any]] = []
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
            logger.warning("Could not parse CheckRun", exc_info=True)
    return check_runs


def get_head_exists(*, pr: Dict[str, Any]) -> bool:
    try:
        return bool(pr["headRef"]["id"])
    except (KeyError, TypeError):
        return False


def get_valid_merge_methods(*, repo: Dict[str, Any]) -> List[MergeMethod]:
    valid_merge_methods: List[MergeMethod] = []
    if repo.get("mergeCommitAllowed"):
        valid_merge_methods.append(MergeMethod.merge)

    if repo.get("rebaseMergeAllowed"):
        valid_merge_methods.append(MergeMethod.rebase)

    if repo.get("squashMergeAllowed"):
        valid_merge_methods.append(MergeMethod.squash)
    return valid_merge_methods


class MergeBody(TypedDict):
    merge_method: str
    commit_title: Optional[str]
    commit_message: Optional[str]


def create_root_config_file_expression(branch: str) -> str:
    return f"{branch}:{CONFIG_FILE_NAME}"


def create_github_config_file_expression(branch: str) -> str:
    return f"{branch}:.github/{CONFIG_FILE_NAME}"


class Ref(pydantic.BaseModel):
    ref: str


class GetOpenPullRequestsResponseSchema(pydantic.BaseModel):
    number: int
    base: Ref


class SubscriptionExpired(pydantic.BaseModel):
    kind: Literal["subscription_expired"] = "subscription_expired"


class TrialExpired(pydantic.BaseModel):
    kind: Literal["trial_expired"] = "trial_expired"


class SeatsExceeded(pydantic.BaseModel):
    kind: Literal["seats_exceeded"] = "seats_exceeded"
    # a list of github account user ids that occupy seats. These users will
    # be allowed to use Kodiak while any new users will be blocked by the
    # paywall.
    allowed_user_ids: List[int]


@dataclass
class Subscription:
    account_id: str
    subscription_blocker: Optional[
        Union[SubscriptionExpired, TrialExpired, SeatsExceeded]
    ]


@dataclass
class CfgInfo:
    parsed: V1 | pydantic.ValidationError | toml.TomlDecodeError
    text: str
    file_expression: str


class ThrottlerProtocol(Protocol):
    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        ...


class Client:
    throttler: ThrottlerProtocol

    def __init__(self, *, owner: str, repo: str, installation_id: str):

        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        # NOTE: We must call `await session.close()` when we are finished with our session.
        # We implement an async context manager this handle this.
        self.session = http.AsyncClient(
            # infinite timeout to match behavior of old, requests_async http
            # client. As a backup we have an asyncio timeout of 30 seconds.
            timeout=None
        )
        self.session.headers[
            "Accept"
        ] = "application/vnd.github.antiope-preview+json,application/vnd.github.merge-info-preview+json"
        if (
            conf.GITHUB_API_HEADER_NAME is not None
            and conf.GITHUB_API_HEADER_VALUE is not None
        ):
            self.session.headers[
                conf.GITHUB_API_HEADER_NAME
            ] = conf.GITHUB_API_HEADER_VALUE
        self.log = logger.bind(
            owner=self.owner, repo=self.repo, install=self.installation_id
        )

    async def __aenter__(self) -> Client:
        self.throttler = get_thottler_for_installation(
            installation_id=self.installation_id
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.session.aclose()

    async def send_query(
        self,
        query: str,
        variables: Mapping[str, Union[str, int, None]],
        installation_id: str,
    ) -> Optional[GraphQLResponse]:
        log = self.log

        token = await get_token_for_install(
            session=self.session, installation_id=installation_id
        )
        self.session.headers["Authorization"] = f"Bearer {token}"
        async with self.throttler:
            res = await self.session.post(
                conf.GITHUB_V4_API_URL, json=(dict(query=query, variables=variables))
            )
        rate_limit_remaining = res.headers.get("x-ratelimit-remaining")
        rate_limit_max = res.headers.get("x-ratelimit-limit")
        rate_limit = f"{rate_limit_remaining}/{rate_limit_max}"
        log = log.bind(rate_limit=rate_limit)
        try:
            res.raise_for_status()
        except http.HTTPError:
            log.warning("github api request error", res=res, exc_info=True)
            return None
        return cast(GraphQLResponse, res.json())

    async def get_permissions_for_username(self, username: str) -> Permission:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        async with self.throttler:
            res = await self.session.get(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/collaborators/{username}/permission"
                ),
                headers=headers,
            )
        log = self.log.bind(res=res, username=username)
        try:
            res.raise_for_status()
        except http.HTTPError:
            log.warning("get_permissions request_failure", exc_info=True)
            return Permission.NONE

        try:
            return Permission(res.json()["permission"])
        except (IndexError, TypeError, ValueError):
            log.exception("get_permissions parse error")
            return Permission.NONE

    # TODO(chdsbd): We may want to cache this response to improve performance as
    # we could encounter a lot of throttling when hitting the Github API
    async def get_reviewers_and_permissions(
        self, *, reviews: List[PRReviewSchema]
    ) -> List[PRReview]:
        reviewer_names: Set[str] = {
            review.author.login
            for review in reviews
            if review.author and review.author.type != Actor.Bot
        }

        bot_reviews: List[PRReview] = []
        for review in reviews:
            if not review.author:
                continue
            if review.author.type == Actor.User:
                reviewer_names.add(review.author.login)
            elif review.author.type == Actor.Bot:
                # Bots either have read or write permissions for a pull request,
                # so if they've been able to write a review on a PR, their
                # review counts as a user with write access.
                bot_reviews.append(
                    PRReview(
                        state=review.state,
                        createdAt=review.createdAt,
                        author=PRReviewAuthor(
                            login=review.author.login, permission=Permission.WRITE
                        ),
                    )
                )

        requests = [
            self.get_permissions_for_username(username) for username in reviewer_names
        ]
        permissions = await asyncio.gather(*requests)

        user_permission_mapping = {
            username: permission
            for username, permission in zip(reviewer_names, permissions)
        }

        return sorted(
            bot_reviews
            + [
                PRReview(
                    state=review.state,
                    createdAt=review.createdAt,
                    author=PRReviewAuthor(
                        login=review.author.login,
                        permission=user_permission_mapping[review.author.login],
                    ),
                )
                for review in reviews
                if review.author and review.author.type == Actor.User
            ],
            key=lambda x: x.createdAt,
        )

    async def get_config_for_ref(self, *, ref: str) -> CfgInfo | None:
        root_config_file_expression = create_root_config_file_expression(branch=ref)
        github_config_file_expression = create_github_config_file_expression(branch=ref)
        res = await self.send_query(
            query=GET_CONFIG_QUERY,
            variables=dict(
                owner=self.owner,
                repo=self.repo,
                rootConfigFileExpression=root_config_file_expression,
                githubConfigFileExpression=github_config_file_expression,
            ),
            installation_id=self.installation_id,
        )
        if res is None:
            return None
        data = res.get("data")
        errors = res.get("errors")
        if errors is not None or data is None:
            self.log.error("could not fetch default branch name", res=res)
            return None
        try:
            parsed = ConfigQueryResponse.parse_obj(data)
        except pydantic.ValidationError:
            self.log.exception("problem parsing api response for config")
            return None

        if not parsed.repository:
            return None
        if (
            parsed.repository.rootConfigFile is not None
            and parsed.repository.rootConfigFile.text is not None
        ):
            config_file_expression = root_config_file_expression
            config_text = parsed.repository.rootConfigFile.text
        elif (
            parsed.repository.githubConfigFile is not None
            and parsed.repository.githubConfigFile.text is not None
        ):
            config_file_expression = github_config_file_expression
            config_text = parsed.repository.githubConfigFile.text
        else:
            return None

        return CfgInfo(
            parsed=V1.parse_toml(config_text),
            text=config_text,
            file_expression=config_file_expression,
        )

    async def get_event_info(self, pr_number: int) -> Optional[EventInfoResponse]:
        """
        Retrieve all the information we need to evaluate a pull request

        This is basically the "do-all-the-things" query
        """

        log = self.log.bind(pr=pr_number)

        res = await self.send_query(
            query=GET_EVENT_INFO_QUERY,
            variables=dict(owner=self.owner, repo=self.repo, PRNumber=pr_number),
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

        subscription = await self.get_subscription()

        pull_request = get_pull_request(repo=repository)
        if not pull_request:
            log.warning("Could not find PR")
            return None

        # update the dictionary to match what we need for parsing
        pull_request["labels"] = get_labels(pr=pull_request)
        pull_request["latest_sha"] = get_sha(pr=pull_request)
        pull_request["number"] = pr_number
        try:
            pr = PullRequest.parse_obj(pull_request)
        except ValueError:
            log.warning("Could not parse pull request")
            return None

        cfg = await self.get_config_for_ref(ref=pr.baseRefName)
        if cfg is None:
            log.info("no config found")
            return None
        branch_protection = get_branch_protection(
            repo=repository, ref_name=pr.baseRefName
        )

        partial_reviews = get_reviews(pr=pull_request)
        reviews_with_permissions = await self.get_reviewers_and_permissions(
            reviews=partial_reviews
        )
        return EventInfoResponse(
            config=cfg.parsed,
            config_str=cfg.text,
            config_file_expression=cfg.file_expression,
            pull_request=pr,
            repository=RepoInfo(
                merge_commit_allowed=repository.get("mergeCommitAllowed", False),
                rebase_merge_allowed=repository.get("rebaseMergeAllowed", False),
                squash_merge_allowed=repository.get("squashMergeAllowed", False),
                delete_branch_on_merge=repository.get("deleteBranchOnMerge") is True,
                is_private=repository.get("isPrivate") is True,
            ),
            subscription=subscription,
            branch_protection=branch_protection,
            review_requests=get_requested_reviews(pr=pull_request),
            reviews=reviews_with_permissions,
            status_contexts=get_status_contexts(pr=pull_request),
            commits=get_commits(pr=pull_request),
            check_runs=get_check_runs(pr=pull_request),
            head_exists=get_head_exists(pr=pull_request),
            valid_merge_methods=get_valid_merge_methods(repo=repository),
        )

    async def get_open_pull_requests(
        self, base: Optional[str] = None, head: Optional[str] = None
    ) -> Optional[List[GetOpenPullRequestsResponseSchema]]:
        """
        https://developer.github.com/v3/pulls/#list-pull-requests
        """
        log = self.log.bind(base=base, head=head)
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        params = dict(state="open", sort="updated", per_page="100")
        if base is not None:
            params["base"] = base
        if head is not None:
            params["head"] = head

        open_prs = []

        page = None
        current_page = 0
        while page != []:
            current_page += 1
            if current_page > 20:
                log.info("hit pagination limit")
                break

            params["page"] = str(current_page)
            async with self.throttler:
                res = await self.session.get(
                    conf.v3_url(f"/repos/{self.owner}/{self.repo}/pulls"),
                    params=params,
                    headers=headers,
                )
            try:
                res.raise_for_status()
            except http.HTTPError:
                log.warning("problem finding prs", res=res, exc_info=True)
                return None

            page = res.json()
            open_prs += [GetOpenPullRequestsResponseSchema.parse_obj(pr) for pr in page]

        return open_prs

    async def delete_branch(self, branch: str) -> http.Response:
        """
        delete a branch by name
        """
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        ref = urllib.parse.quote(f"heads/{branch}")
        async with self.throttler:
            return await self.session.delete(
                conf.v3_url(f"/repos/{self.owner}/{self.repo}/git/refs/{ref}"),
                headers=headers,
            )

    async def update_branch(self, *, pull_number: int) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        async with self.throttler:
            return await self.session.put(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pull_number}/update-branch"
                ),
                headers=headers,
            )

    async def approve_pull_request(self, *, pull_number: int) -> http.Response:
        """
        https://developer.github.com/v3/pulls/reviews/#create-a-pull-request-review
        """
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        body = dict(event="APPROVE")
        async with self.throttler:
            return await self.session.post(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/pulls/{pull_number}/reviews"
                ),
                headers=headers,
                json=body,
            )

    async def get_pull_request(self, number: int) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        url = conf.v3_url(f"/repos/{self.owner}/{self.repo}/pulls/{number}")
        async with self.throttler:
            return await self.session.get(url, headers=headers)

    async def merge_pull_request(
        self,
        number: int,
        merge_method: str,
        commit_title: Optional[str],
        commit_message: Optional[str],
    ) -> http.Response:
        body = dict(merge_method=merge_method)
        # we must not pass the keys for commit_title or commit_message when they
        # are null because GitHub will error saying the title/message cannot be
        # null. When the keys are not passed, GitHub creates a title and
        # message.
        if commit_title is not None:
            body["commit_title"] = commit_title
        if commit_message is not None:
            body["commit_message"] = commit_message
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        url = conf.v3_url(f"/repos/{self.owner}/{self.repo}/pulls/{number}/merge")
        async with self.throttler:
            return await self.session.put(url, headers=headers, json=body)

    async def update_ref(self, *, ref: str, sha: str) -> http.Response:
        """
        https://docs.github.com/en/rest/reference/git#update-a-reference
        """
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        url = conf.v3_url(f"/repos/{self.owner}/{self.repo}/git/refs/heads/{ref}")
        async with self.throttler:
            return await self.session.patch(url, headers=headers, json=dict(sha=sha))

    async def create_notification(
        self, head_sha: str, message: str, summary: Optional[str] = None
    ) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        url = conf.v3_url(f"/repos/{self.owner}/{self.repo}/check-runs")
        body = dict(
            name=CHECK_RUN_NAME,
            head_sha=head_sha,
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            conclusion="neutral",
            output=dict(title=message, summary=summary or ""),
        )
        async with self.throttler:
            return await self.session.post(url, headers=headers, json=body)

    async def add_label(self, label: str, pull_number: int) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        async with self.throttler:
            return await self.session.post(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/issues/{pull_number}/labels"
                ),
                json=dict(labels=[label]),
                headers=headers,
            )

    async def delete_label(self, label: str, pull_number: int) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        escaped_label = urllib.parse.quote(label)
        async with self.throttler:
            return await self.session.delete(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/issues/{pull_number}/labels/{escaped_label}"
                ),
                headers=headers,
            )

    async def create_comment(self, body: str, pull_number: int) -> http.Response:
        headers = await get_headers(
            session=self.session, installation_id=self.installation_id
        )
        async with self.throttler:
            return await self.session.post(
                conf.v3_url(
                    f"/repos/{self.owner}/{self.repo}/issues/{pull_number}/comments"
                ),
                json=dict(body=body),
                headers=headers,
            )

    async def get_subscription(self) -> Optional[Subscription]:
        """
        Get subscription information for installation.
        """
        from kodiak.queue import get_redis

        redis = await get_redis()
        res = await redis.hgetall(
            f"kodiak:subscription:{self.installation_id}".encode()
        )
        if not res:
            return None
        real_response = await res.asdict()
        if not real_response:
            return None
        subscription_blocker_kind = (
            real_response.get(b"subscription_blocker") or b""
        ).decode()
        subscription_blocker: Optional[
            Union[SubscriptionExpired, TrialExpired, SeatsExceeded]
        ] = None
        if subscription_blocker_kind == "seats_exceeded":
            # to be backwards compatible we must handle the case of `data` missing.
            try:
                subscription_blocker = SeatsExceeded.parse_raw(
                    # Pydantic says it doesn't allow Nones, but passing a None
                    # raises a ValidationError which is fine.
                    real_response.get(b"data")  # type: ignore
                )
            except pydantic.ValidationError:
                logger.exception("failed to parse seats_exceeded data", exc_info=True)
                subscription_blocker = SeatsExceeded(allowed_user_ids=[])
        if subscription_blocker_kind == "trial_expired":
            subscription_blocker = TrialExpired()
        if subscription_blocker_kind == "subscription_expired":
            subscription_blocker = SubscriptionExpired()
        return Subscription(
            account_id=real_response[b"account_id"].decode(),
            subscription_blocker=subscription_blocker,
        )


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


async def get_token_for_install(
    *, session: http.AsyncClient, installation_id: str
) -> str:
    """
    https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-an-installation
    """
    token = installation_cache.get(installation_id)
    if token is not None and not token.expired:
        return token.token
    app_token = generate_jwt(
        private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID
    )
    throttler = get_thottler_for_installation(
        # this isn't a real installation ID, but it provides rate limiting
        # for our GithubApp instead of the installations we typically act as
        installation_id=APPLICATION_ID
    )
    async with throttler:
        res = await session.post(
            conf.v3_url(f"/app/installations/{installation_id}/access_tokens"),
            headers=dict(
                Accept="application/vnd.github.machine-man-preview+json",
                Authorization=f"Bearer {app_token}",
            ),
        )
    assert res.status_code < 300
    token_response = TokenResponse(**res.json())
    installation_cache[installation_id] = token_response
    return token_response.token


async def get_headers(
    *, session: http.AsyncClient, installation_id: str
) -> dict[str, str]:
    token = await get_token_for_install(
        session=session, installation_id=installation_id
    )
    return dict(
        Authorization=f"token {token}",
        Accept="application/vnd.github.machine-man-preview+json,application/vnd.github.antiope-preview+json,application/vnd.github.lydian-preview+json",
    )


__all__ = ["Commit", "GitActor", "CommitConnection", "PullRequestCommitUser"]
