from typing import List

import pydantic

from kodiak.events.base import GithubEvent


class Commit(pydantic.BaseModel):
    sha: str


class Branch(pydantic.BaseModel):
    name: str
    commit: Commit


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class StatusEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#statusevent
    """

    id: int
    sha: str
    branches: List[Branch]
    repository: Repository
