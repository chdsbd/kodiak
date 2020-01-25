from typing import Mapping,Type

from kodiak.events.base import GithubEvent
from kodiak.events.push import PushEvent

event_mapping: Mapping[str, Type[GithubEvent]] = {"push": PushEvent}
