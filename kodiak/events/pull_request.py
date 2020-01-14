import pydantic

from kodiak.events.base import GithubEvent


class User(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: User


class PullRequestEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestevent
    """

    number: int
    repository: Repository
    sender: User
