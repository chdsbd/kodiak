import pydantic

from kodiak.events.base import GithubEvent


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class PullRequestEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestevent
    """

    number: int
    repository: Repository
