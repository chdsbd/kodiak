import pydantic

from kodiak.events.base import GithubEvent


class PullRequest(pydantic.BaseModel):
    number: int


class User(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: User


class PullRequestReviewEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pullrequestreviewevent
    """

    pull_request: PullRequest
    repository: Repository
