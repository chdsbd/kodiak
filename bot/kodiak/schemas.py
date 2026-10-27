from __future__ import annotations

from typing import Any, Dict, Optional

import pydantic


class RawWebhookEvent(pydantic.BaseModel):
    event_name: str
    payload: Dict[str, Any]
    # unix timestamp when ingest received the webhook. Optional for events queued
    # before this field was added.
    received_at: Optional[float] = None
