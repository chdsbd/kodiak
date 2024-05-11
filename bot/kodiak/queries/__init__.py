from __future__ import annotations

import urllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Union, cast

import jwt
import pydantic
import structlog
import toml
from mypy_extensions import TypedDict
from pydantic import BaseModel
from typing_extensions import Literal, Protocol

import kodiak.app_config as conf
from kodiak import http
from kodiak.config import V1, MergeMethod
from kodiak.http import HttpClient
from kodiak.queries.commits import Commit, CommitConnection, GitActor
from kodiak.queries.commits import User as PullRequestCommitUser
from kodiak.queries.commits import get_commits
from kodiak.redis_client import redis_web_api
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


class GraphQLResponse(TypedDict, total=False):
    data: Optional[Dict[Any, Any]]
    errors: Optional[List[GraphQLError]]


GET_CONFIG_QUERY = """
query (
    $owner: String!,
    $repo: String!,
    $rootConfigFileExpression: String!,
    $githubConfigFileExpression: String!,
    $orgRootConfigFileExpression: String,
    $orgGithubConfigFileExpression: String
  ) {
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
  orgConfigRepo: repository(owner: $owner, name: ".github") {
    rootConfigFile: object(expression: $orgRootConfigFileExpression) {
      ... on Blob {
        text
      }
    }
    githubConfigFile: object(expression: $orgGithubConfigFileExpression) {
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

    def __bool__(self) -> bool:
        return bool(self.rootConfigFile or self.githubConfigFile)


class ConfigQueryResponse(pydantic.BaseModel):
    repository: Optional[ConfigQueryOptions]
    orgConfigRepo: Optional[ConfigQueryOptions]


@dataclass
class ParsedConfig:
    text: str
    kind: Literal["repo_root", "repo_github", "org_root", "org_github"]


def parse_config(data: dict[Any, Any]) -> ParsedConfig | None:
    try:
        res = ConfigQueryResponse.parse_obj(data)
    except pydantic.ValidationError:
        logger.exception("problem parsing api response for config")
        return None

    if res.repository:
        if (
            res.repository.rootConfigFile
            and res.repository.rootConfigFile.text is not None
        ):
            return ParsedConfig(
                text=res.repository.rootConfigFile.text, kind="repo_root"
            )
        if (
            res.repository.githubConfigFile
            and res.repository.githubConfigFile.text is not None
        ):
            return ParsedConfig(
                text=res.repository.githubConfigFile.text, kind="repo_github"
            )
        raise Exception("unexpected missing config file")
    if res.orgConfigRepo:
        if (
            res.orgConfigRepo.rootConfigFile
            and res.orgConfigRepo.rootConfigFile.text is not None
        ):
            return ParsedConfig(
                text=res.orgConfigRepo.rootConfigFile.text, kind="org_root"
            )
        if (
            res.orgConfigRepo.githubConfigFile
            and res.orgConfigRepo.githubConfigFile.text is not None
        ):
            return ParsedConfig(
                text=res.orgConfigRepo.githubConfigFile.text, kind="org_github"
            )
        raise Exception("unexpected missing config file")
    return None


def get_event_info_query(
    requires_conversation_resolution: bool, fetch_body_html: bool
) -> str:
    return """
query GetEventInfo($owner: String!, $repo: String!, $PRNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    branchProtectionRules(first: 100) {
      nodes {
        matchingRefs(first: 100) {
          nodes {
            name
          }
        }
        requiresStatusChecks
        requiredStatusCheckContexts
        requiresStrictStatusChecks
        requiresCommitSignatures
        %(requiresConversationResolution)s
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
          asCodeOwner
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
      %(bodyHTMLQuery)s
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
  orgConfigRepo: repository(owner: $owner, name: ".github") {
    defaultBranchRef {
      name
    }
  }
}

""" % dict(
        requiresConversationResolution="requiresConversationResolution"
        if requires_conversation_resolution
        else "",
        bodyHTMLQuery="bodyHTML" if fetch_body_html else "bodyHTML: body",
    )


def get_org_config_default_branch(data: dict[Any, Any]) -> str | None:
    try:
        return cast(Union[str, None], data["orgConfigRepo"]["defaultBranchRef"]["name"])
    except (KeyError, TypeError):
        return None


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
    author: Optional[PullRequestAuthor]
    isDraft: bool
    mergeStateStatus: MergeStateStatus
    # null if the pull request does not require a review (no branch protection
    # rule). Otherwise shows if the pull request meets the branch protection
    # requirements.
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
    bot_reviews: List[PRReview] = field(default_factory=list)
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

    requiresStatusChecks: bool
    requiredStatusCheckContexts: List[str]
    requiresStrictStatusChecks: bool
    requiresCommitSignatures: bool
    requiresConversationResolution: Optional[bool]
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
    asCodeOwner: bool = False


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
            asCodeOwner = request_dict["asCodeOwner"]
            request = request_dict["requestedReviewer"]
            if request is None:
                continue
            typename = request["__typename"]
            if typename in {"User", "Mannequin"}:
                name = request["login"]
            else:
                name = request["name"]
            review_requests.append(
                PRReviewRequest(name=name, asCodeOwner=bool(asCodeOwner))
            )
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
    check_run_dicts: List[Dict[str, Any] | None] = []
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
        if check_run_dict is None:
            continue
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


@dataclass
class ApiFeatures:
    requires_conversation_resolution: bool


def has_body_html_error(errors: list[GraphQLError]) -> bool:
    for error in errors:
        if (
            error.get("type") == "FORBIDDEN"
            and error.get("message") == "Resource not accessible by integration"
            and error.get("path") == ["repository", "pullRequest", "headRef"]
        ):
            return True
    return False


_api_features_cache: ApiFeatures | None = None


class ThrottlerProtocol(Protocol):
    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        ...


class SecondaryRateLimit(Exception):
    ...


class Client:
    throttler: ThrottlerProtocol

    def __init__(self, *, owner: str, repo: str, installation_id: str):

        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        # NOTE: We must call `await session.close()` when we are finished with our session.
        # We implement an async context manager this handle this.
        self.session = HttpClient(
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
        self.throttler = await get_thottler_for_installation(
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
            if (
                res.status_code == 403
                and b"You have exceeded a secondary rate limit" in res.content
            ):
                raise SecondaryRateLimit()
            log.warning("github api request error", res=res, exc_info=True)
            return None
        return cast(GraphQLResponse, res.json())

    async def get_api_features(self) -> ApiFeatures | None:
        """
        Check if we can use recently added schema fields.

        For GitHub Enterprise installations, the latest GraphQL fields may not
        be available.

        To query the GraphQL API, we need an installation token, so for the
        first client to make an API request, we use their credentials to view
        schema metadata and cache the results.
        """
        global _api_features_cache  # pylint: disable=global-statement
        if _api_features_cache is not None:
            return _api_features_cache
        res = await self.send_query(
            query="""
query {
   __type(name:"BranchProtectionRule") {
      fields(includeDeprecated: true) {
         name
      }
   }
}
""",
            variables=dict(),
            installation_id=self.installation_id,
        )
        if res is None:
            self.log.warning("failed to fetching api features")
            return None
        errors = res.get("errors")
        data = res.get("data")
        if errors or not data:
            self.log.warning("errors fetching api features", errors=errors, data=data)
            return None

        try:
            fields = data["__type"]["fields"]
        except (TypeError, KeyError):
            self.log.warning("problem parsing api features", exc_info=True)
            return None
        _api_features_cache = ApiFeatures(
            requires_conversation_resolution=any(
                field["name"] == "requiresConversationResolution" for field in fields
            )
        )
        return _api_features_cache

    def get_bot_reviews(self, *, reviews: List[PRReviewSchema]) -> List[PRReview]:
        bot_reviews: List[PRReview] = []
        for review in reviews:
            if not review.author:
                continue
            if review.author.type == Actor.Bot:
                # Bots either have read or write permissions for a pull request,
                # so if they've been able to write a review on a PR, their
                # review counts as a user with write access.
                bot_reviews.append(
                    PRReview(
                        state=review.state,
                        createdAt=review.createdAt,
                        author=PRReviewAuthor(login=review.author.login),
                    )
                )

        return sorted(
            bot_reviews,
            key=lambda x: x.createdAt,
        )

    async def get_config_for_ref(
        self, *, ref: str, org_repo_default_branch: str | None
    ) -> CfgInfo | None:
        repo_root_config_expression = create_root_config_file_expression(branch=ref)
        repo_github_config_expression = create_github_config_file_expression(branch=ref)
        org_root_config_expression: str | None = None
        org_github_config_file_expression: str | None = None

        if org_repo_default_branch is not None:
            org_root_config_expression = create_root_config_file_expression(
                branch=org_repo_default_branch
            )
            org_github_config_file_expression = create_github_config_file_expression(
                branch=org_repo_default_branch
            )
        res = await self.send_query(
            query=GET_CONFIG_QUERY,
            variables=dict(
                owner=self.owner,
                repo=self.repo,
                rootConfigFileExpression=repo_root_config_expression,
                githubConfigFileExpression=repo_github_config_expression,
                orgRootConfigFileExpression=org_root_config_expression,
                orgGithubConfigFileExpression=org_github_config_file_expression,
            ),
            installation_id=self.installation_id,
        )
        if res is None:
            return None
        data = res.get("data")
        if data is None:
            self.log.error("could not fetch default branch name", res=res)
            return None

        parsed_config = parse_config(data)
        if parsed_config is None:
            return None

        def get_file_expression() -> str:
            assert parsed_config is not None
            if parsed_config.kind == "repo_root":
                return repo_root_config_expression
            if parsed_config.kind == "repo_github":
                return repo_github_config_expression
            if parsed_config.kind == "org_root":
                assert org_root_config_expression is not None
                return org_root_config_expression
            if parsed_config.kind == "org_github":
                assert org_github_config_file_expression is not None
                return org_github_config_file_expression
            raise Exception(f"unknown config kind {parsed_config.kind!r}")

        return CfgInfo(
            parsed=V1.parse_toml(parsed_config.text),
            text=parsed_config.text,
            file_expression=get_file_expression(),
        )

    async def get_event_info(self, pr_number: int) -> Optional[EventInfoResponse]:
        """
        Retrieve all the information we need to evaluate a pull request

        This is basically the "do-all-the-things" query
        """

        log = self.log.bind(pr=pr_number)

        api_features = await self.get_api_features()

        res = await self.send_query(
            query=get_event_info_query(
                requires_conversation_resolution=api_features.requires_conversation_resolution
                if api_features
                else True,
                fetch_body_html=True,
            ),
            variables=dict(owner=self.owner, repo=self.repo, PRNumber=pr_number),
            installation_id=self.installation_id,
        )
        if res is None:
            return None

        data = res.get("data")
        if data is None:
            log.error("could not fetch event info", res=res)
            return None

        # NOTE(chdsbd): The GitHub GraphQL API has a bug where querying for
        # the bodyHTML field sometimes breaks and returns errors. I don't know why and I've tried to talk with GitHub Support.
        #
        # In these cases, we retry without the bodyHTML edge. Instead we map the markdown body edge to bodyHTML. This let's us workaround the issue.
        #
        # I think it's better to revert to using the markdown body for bodyHTML instead of failing to merge the PR completely.
        errors = res.get("errors")
        if errors is not None and has_body_html_error(errors):
            log.info("has_body_html_error")
            res = await self.send_query(
                query=get_event_info_query(
                    requires_conversation_resolution=api_features.requires_conversation_resolution
                    if api_features
                    else True,
                    fetch_body_html=False,
                ),
                variables=dict(owner=self.owner, repo=self.repo, PRNumber=pr_number),
                installation_id=self.installation_id,
            )
            if res is None:
                return None

            data = res.get("data")
            if data is None:
                log.error("could not fetch event info", res=res)
                return None

        repository = get_repo(data=data)
        if not repository:
            log.warning("could not find repository")
            return None

        org_repo_default_branch = get_org_config_default_branch(data=data)

        subscription = (
            await self.get_subscription() if conf.SUBSCRIPTIONS_ENABLED else None
        )

        pull_request = get_pull_request(repo=repository)
        if not pull_request:
            log.warning("Could not find PR")
            return None

        latest_sha = get_sha(pr=pull_request)
        if latest_sha is None:
            # PR didn't have a diff associated with it!
            log.info("pull request missing sha")
            return None

        # update the dictionary to match what we need for parsing
        pull_request["labels"] = get_labels(pr=pull_request)
        pull_request["latest_sha"] = latest_sha
        pull_request["number"] = pr_number
        try:
            pr = PullRequest.parse_obj(pull_request)
        except ValueError:
            log.warning("Could not parse pull request")
            return None

        cfg = await self.get_config_for_ref(
            ref=pr.baseRefName, org_repo_default_branch=org_repo_default_branch
        )
        if cfg is None:
            log.info("no config found")
            return None
        branch_protection = get_branch_protection(
            repo=repository, ref_name=pr.baseRefName
        )

        all_reviews = get_reviews(pr=pull_request)
        bot_reviews = self.get_bot_reviews(reviews=all_reviews)
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
            bot_reviews=bot_reviews,
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
        res = await redis_web_api.hgetall(
            f"kodiak:subscription:{self.installation_id}".encode()
        )
        if not res:
            return None
        subscription_blocker_kind = (res.get(b"subscription_blocker") or b"").decode()
        subscription_blocker: Optional[
            Union[SubscriptionExpired, TrialExpired, SeatsExceeded]
        ] = None
        if subscription_blocker_kind == "seats_exceeded":
            # to be backwards compatible we must handle the case of `data` missing.
            try:
                subscription_blocker = SeatsExceeded.parse_raw(
                    # Pydantic says it doesn't allow Nones, but passing a None
                    # raises a ValidationError which is fine.
                    res.get(b"data")  # type: ignore
                )
            except pydantic.ValidationError:
                logger.exception("failed to parse seats_exceeded data", exc_info=True)
                subscription_blocker = SeatsExceeded(allowed_user_ids=[])
        if subscription_blocker_kind == "trial_expired":
            subscription_blocker = TrialExpired()
        if subscription_blocker_kind == "subscription_expired":
            subscription_blocker = SubscriptionExpired()
        return Subscription(
            account_id=res[b"account_id"].decode(),
            subscription_blocker=subscription_blocker,
        )


def generate_jwt(*, private_key: str, app_identifier: str) -> str:
    """
    Create an authentication token to make application requests.
    https://developer.github.com/apps/building-github-apps/authenticating-with-github-apps/#authenticating-as-a-github-app

    This is different from authenticating as an installation
    """
    issued_at = int(datetime.now().timestamp())
    expiration = int((datetime.now() + timedelta(minutes=9, seconds=30)).timestamp())
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
    throttler = await get_thottler_for_installation(
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
    if res.status_code > 300:
        raise Exception(f"Failed to get token, github response: {res.text}")
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
