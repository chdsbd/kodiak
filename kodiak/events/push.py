from kodiak.events.base import GithubEvent
import pydantic

class User(pydantic.BaseModel):
    login: str

class Repository(pydantic.BaseModel):
    name: str
    owner: User

class PushEvent(GithubEvent):
    """
    https://developer.github.com/v3/activity/events/types/#pushevent
    """

    ref: str
    repository: Repository
