from dataclasses import dataclass
from typing import Any, List, MutableMapping

EventDictType = MutableMapping[str, Any]


@dataclass
class DropLoggerKeys:
    """
    follows the protocol for structlog's processors
    """

    keys: List[str]

    def __call__(
        self, logger: Any, method_name: str, event_dict: EventDictType
    ) -> EventDictType:
        for k in self.keys:
            event_dict.pop(k, None)
        return event_dict
