"""
Schemas for Github webhook events. These models are incomplete.
"""
from datetime import datetime
import typing
import pydantic
from pydantic import UrlStr
from enum import Enum
from typing_extensions import Literal


AnyDict = typing.Dict[typing.Any, typing.Any]

event_registry: typing.MutableMapping[str, typing.Type["GithubEvent"]] = dict()


def register(cls: typing.Type["GithubEvent"]):
    event_registry[cls._event_name] = cls
    return cls


class HookConfiguration(pydantic.BaseModel):
    url: UrlStr
    content_type: str
    insecure_url: typing.Optional[str]


class Hook(pydantic.BaseModel):
    """
    https://developer.github.com/v3/repos/hooks/#get-single-hook
    """

    id: int
    name: str
    events: typing.List[str]
    active: bool
    config: HookConfiguration
    updated_at: datetime
    created_at: datetime


class GithubEvent(pydantic.BaseModel):
    _event_name: str


@register
class Ping(GithubEvent):
    """
    https://developer.github.com/webhooks/#ping-event
    """

    _event_name = "ping"
    zen: str
    hook_id: int
    hook: Hook


class UserType(Enum):
    user = "User"
    organization = "Organization"


class User(pydantic.BaseModel):
    login: str
    id: int
    node_id: str
    url: UrlStr
    type: UserType


class Repo(pydantic.BaseModel):
    id: int
    node_id: str
    name: str
    full_name: str
    owner: User
    private: bool
    description: typing.Optional[str]
    fork: bool
    url: UrlStr
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
    homepage: typing.Optional[UrlStr]
    default_branch: str


class CompareBranch(pydantic.BaseModel):
    label: str
    ref: str
    sha: str
    user: User
    repo: Repo


class PullRequestState(Enum):
    open = "open"
    closed = "closed"


class Label(pydantic.BaseModel):
    id: int
    node_id: str
    url: UrlStr
    name: str
    color: str
    default: bool = False


class BasePullRequest(pydantic.BaseModel):
    url: UrlStr
    id: int
    node_id: str
    number: int
    state: PullRequestState
    locked: bool
    title: str
    user: User
    body: str
    created_at: datetime
    updated_at: datetime
    closed_at: typing.Optional[datetime]
    merged_at: typing.Optional[datetime]
    merge_commit_sha: typing.Optional[str]
    assignee: typing.Optional[str]
    assignees: typing.List[str]
    requested_reviewers: typing.List[str]
    requested_teams: typing.List[str]
    labels: typing.List[Label]
    milestone: typing.Optional[str]
    head: CompareBranch
    base: CompareBranch


class MergeableState(Enum):
    # The pull request is behind target
    behind = "behind"
    blocked = "blocked"
    # The pull request can be merged.
    clean = "clean"
    # The pull request cannot be merged due to merge conflicts.
    conflicting = "dirty"
    # The mergeability of the pull request is still being calculated.
    unknown = "unknown"
    unstable = "unstable"


class PullRequest(BasePullRequest):
    merged: bool
    mergeable: bool
    rebaseable: bool
    mergeable_state: MergeableState
    merged_by: typing.Optional[User]
    comments: int
    review_comments: int
    maintainer_can_modify: bool
    commits: int
    additions: int
    deletions: int
    changed_files: int


class PullRequestEventActions(Enum):
    assigned = "assigned"
    unassigned = "unassigned"
    review_requested = "review_requested"
    review_request_removed = "review_request_removed"
    labeled = "labeled"
    unlabeled = "unlabeled"
    opened = "opened"
    edited = "edited"
    closed = "closed"
    ready_for_review = "ready_for_review"
    locked = "locked"
    unlocked = "unlocked"
    reopened = "reopened"


@register
class PullRequestEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestevent
    """

    _event_name = "pull_request"
    action: PullRequestEventActions
    number: int
    pull_request: PullRequest
    repository: Repo
    sender: User


class PullRequestReviewAction(Enum):
    submitted = "submitted"
    edited = "edited"
    dismissed = "dismissed"


class PullRequestReview(pydantic.BaseModel):
    id: int
    node_id: str
    user: User
    body: typing.Optional[str]
    commit_id: str
    submitted_at: datetime
    state: str


class PullRequestShort(BasePullRequest):
    pass


@register
class PullRequestReviewEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestreviewevent
    """

    _event_name = "pull_request_review"
    action: PullRequestReviewAction
    review: PullRequestReview
    pull_request: PullRequestShort
    repository: Repo
    sender: User


class CheckRunStatus(Enum):
    queued = "queued"
    in_progress = "in_progress"
    completed = "completed"


class CheckRunConclusion(Enum):
    success = "success"
    failure = "failure"
    neutral = "neutral"
    cancelled = "cancelled"
    timed_out = "timed_out"
    action_required = "action_required"


class CheckRun(pydantic.BaseModel):
    id: int
    head_sha: str
    external_id: str
    url: UrlStr
    status: CheckRunStatus
    name: str
    conclusion: typing.Optional[CheckRunConclusion]

    def to_status(self) -> Literal["pending", "success", "failure"]:
        if self.status is None:
            return "pending"
        if self.status in (CheckRunConclusion.success, CheckRunConclusion.neutral):
            return "success"
        return "failure"


class CheckRunEventAction(Enum):
    created = "created"
    rerequested = "rerequested"
    completed = "completed"
    requested_action = "requested_action"


@register
class CheckRunEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#checkrunevent
    """

    _event_name = "check_run"
    action: CheckRunEventAction
    check_run: CheckRun
    repository: Repo


class Commiter(pydantic.BaseModel):
    name: str
    email: str
    date: datetime


class Tree(pydantic.BaseModel):
    sha: str
    url: UrlStr


class CommitDetails(pydantic.BaseModel):
    author: Commiter
    commiter: Commiter
    message: str
    tree: Tree
    url: UrlStr
    comment_count: int


class Commit(pydantic.BaseModel):
    sha: str
    node_id: str
    url: UrlStr
    author: User
    committer: User
    parents: typing.List[Tree]


class Branch(pydantic.BaseModel):
    name: str
    commit: Tree


class StatusEventState(Enum):
    pending = "pending"
    success = "success"
    failure = "failure"
    error = "error"


@register
class StatusEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#statusevent
    """

    _event_name = "status"
    id: int
    sha: str
    name: str
    target_url: typing.Optional[UrlStr]
    context: str
    description: typing.Optional[str]
    state: StatusEventState
    commit: Commit
    branches: typing.List[Branch]
    created_at: datetime
    updated_at: datetime
    repository: Repo
    sender: User


class PushEventCommitAuthor(pydantic.BaseModel):
    name: str
    email: str


class PushEventCommit(pydantic.BaseModel):
    sha: str
    message: str
    author: PushEventCommitAuthor
    url: UrlStr
    distinct: bool


@register
class PushEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pushevent
    """

    _event_name = "push"
    ref: str
    before: str
    after: str
    created: bool
    deleted: bool
    forced: bool
    base_ref: typing.Optional[str]
    compare: UrlStr
    commits: typing.List[PushEventCommit]
    head_commit: typing.Optional[PushEventCommit]
    repository: Repo
    pusher: PushEventCommitAuthor
    sender: User
