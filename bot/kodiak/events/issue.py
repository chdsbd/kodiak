from typing import Optional

import pydantic

from kodiak.events.base import GithubEvent


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class Label(pydantic.BaseModel):
    name: str


class Issue(pydantic.BaseModel):
    number: int
    state: str
    labels: list[Label]


class IssueEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#issuesevent
    """

    action: str
    issue: Issue
    repository: Repository
    # For "unlabeled" and "labeled" actions, this contains the label that was changed
    label: Optional[Label] = None
