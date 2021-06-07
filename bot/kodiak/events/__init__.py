import pydantic

from kodiak.events.check_run import CheckRunEvent  # noqa: F401
from kodiak.events.pull_request import PullRequestEvent  # noqa: F401
from kodiak.events.pull_request_review import PullRequestReviewEvent  # noqa: F401
from kodiak.events.push import PushEvent  # noqa: F401
from kodiak.events.status import StatusEvent  # noqa: F401


class RawIncomingEvent(pydantic.BaseModel):
    name: str
    payload: str
