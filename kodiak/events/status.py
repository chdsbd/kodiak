import pydantic

from kodiak.events.base import GithubEvent


class User(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: User


class Commit(pydantic.BaseModel):
    sha: str


class StatusEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#statusevent
    """

    commit: Commit
    repository: Repository
