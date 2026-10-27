from typing import List

import pydantic

from kodiak.events.base import GithubEvent


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class Commit(pydantic.BaseModel):
    added: List[str] = []
    removed: List[str] = []
    modified: List[str] = []


class PushEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pushevent
    """

    ref: str
    repository: Repository
    # GitHub includes at most 20 commits.
    commits: List[Commit] = pydantic.Field(default_factory=list)
