from typing import List

import pydantic

from kodiak.events.base import GithubEvent


class User(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: User


class PullRequest(pydantic.BaseModel):
    number: int


class CheckRun(pydantic.BaseModel):
    name: str
    pull_requests: List[PullRequest]


class CheckRunEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#checkrunevent
    """

    check_run: CheckRun
    repository: Repository
