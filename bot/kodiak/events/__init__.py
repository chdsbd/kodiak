from typing import Mapping, Type

from kodiak.events.base import GithubEvent
from kodiak.events.check_run import CheckRunEvent
from kodiak.events.pull_request import PullRequestEvent
from kodiak.events.pull_request_review import PullRequestReviewEvent
from kodiak.events.push import PushEvent
from kodiak.events.status import StatusEvent

event_schema_mapping: Mapping[str, Type[GithubEvent]] = {
    "check_run": CheckRunEvent,
    "pull_request": PullRequestEvent,
    "pull_request_review": PullRequestReviewEvent,
    "push": PushEvent,
    "status": StatusEvent,
}
