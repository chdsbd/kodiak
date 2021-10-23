from __future__ import annotations

from typing import Any, Dict

import pydantic


class RawWebhookEvent(pydantic.BaseModel):
    event_name: str
    payload: Dict[str, Any]
