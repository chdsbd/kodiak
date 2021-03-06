import pydantic

from kodiak.events.base import GithubEvent


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class Ref(pydantic.BaseModel):
    ref: str


class PullRequest(pydantic.BaseModel):
    base: Ref


class PullRequestEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestevent
    """

    number: int
    pull_request: PullRequest
    repository: Repository
