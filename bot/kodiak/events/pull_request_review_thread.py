import pydantic

from kodiak.events.base import GithubEvent


class Ref(pydantic.BaseModel):
    ref: str


class PullRequest(pydantic.BaseModel):
    number: int
    base: Ref


class Owner(pydantic.BaseModel):
    login: str


class Repository(pydantic.BaseModel):
    name: str
    owner: Owner


class PullRequestReviewThreadEvent(GithubEvent):
    """
    This event is currently undocumented as of 2021-07-20.
    """

    pull_request: PullRequest
    repository: Repository
