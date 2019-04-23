"""
Schemas for Github webhook events. These models are incomplete.
"""
from datetime import datetime
import typing
from pydantic import BaseModel, UrlStr
from enum import Enum


AnyDict = typing.Dict[typing.Any, typing.Any]

event_registry: typing.Mapping[str, BaseModel] = dict()


def register(header_name: str) -> typing.Callable:
    def decorator(cls: BaseModel):
        event_registry[header_name] = cls
        return cls

    return decorator


class HookConfiguration(BaseModel):
    url: UrlStr
    content_type: str
    insecure_url: typing.Optional[str]


class Hook(BaseModel):
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


@register("ping")
class Ping(BaseModel):
    zen: str
    hook_id: int
    hook: Hook


class UserType(Enum):
    user = "User"
    organization = "Organization"


class User(BaseModel):
    login: str
    id: int
    node_id: str
    url: UrlStr
    type: UserType


class Repo(BaseModel):
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


class CompareBranch(BaseModel):
    label: str
    ref: str
    sha: str
    user: User
    repo: Repo


class BasePullRequest(BaseModel):
    url: UrlStr
    id: int
    node_id: str
    number: int
    state: str
    locked: bool
    title: str
    user: User
    body: str
    created_at: datetime
    updated_at: datetime
    closed_at: typing.Optional[datetime]
    merged_at: typing.Optional[datetime]
    merge_commit_sha: str
    assignee: typing.Optional[str]
    assignees: typing.List[str]
    requested_reviewers: typing.List[str]
    requested_teams: typing.List[str]
    labels: typing.List[str]
    milestone: typing.Optional[str]
    head: CompareBranch
    base: CompareBranch


class PullRequest(BasePullRequest):
    merged: bool
    mergeable: bool
    rebaseable: bool
    mergeable_state: str
    merged_by: typing.Optional[str]
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


@register("pull_request")
class PullRequestEvent(BaseModel):
    action: PullRequestEventActions
    number: int
    pull_request: PullRequest
    repository: Repo
    sender: User


class PullRequestReviewAction(Enum):
    submitted = "submitted"
    edited = "edited"
    dismissed = "dismissed"


class PullRequestReview(BaseModel):
    id: int
    node_id: str
    user: User
    body: typing.Optional[str]
    commit_id: str
    submitted_at: datetime
    state: str


class PullRequestShort(BasePullRequest):
    pass


@register("pull_request_review")
class PullRequestReviewEvent(BaseModel):
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


class CheckRun(BaseModel):
    id: int
    head_sha: str
    external_id: str
    url: UrlStr
    status: CheckRunStatus
    conclusion: typing.Optional[CheckRunConclusion]


class CheckRunEventAction(Enum):
    created = "created"
    rerequested = "rerequested"
    completed = "completed"
    requested_action = "requested_action"


@register("check_run")
class CheckRunEvent(BaseModel):
    action: CheckRunEventAction
    check_run: CheckRun
    repository: Repo


class Commiter(BaseModel):
    name: str
    email: str
    date: datetime


class Tree(BaseModel):
    sha: str
    url: UrlStr


class CommitDetails(BaseModel):
    author: Commiter
    commiter: Commiter
    message: str
    tree: Tree
    url: UrlStr
    comment_count: int


class Commit(BaseModel):
    sha: str
    node_id: str
    url: UrlStr
    author: User
    committer: User
    parents: typing.List[Tree]


class Branch(BaseModel):
    name: str
    commit: Tree


class StatusEventState(Enum):
    pending = "pending"
    success = "success"
    failure = "failure"
    error = "error"


@register("status")
class StatusEvent(BaseModel):
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


class PushEventCommitAuthor(BaseModel):
    name: str
    email: str


class PushEventCommit(BaseModel):
    sha: str
    message: str
    author: PushEventCommitAuthor
    url: UrlStr
    distinct: bool


@register("push")
class PushEvent(BaseModel):
    # TODO: Is this more useful or the name in the decorator?
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


UNION_EVENTS = typing.Union[PullRequestEvent, PushEvent]

ALL_EVENTS = [PullRequestEvent, PushEvent]
