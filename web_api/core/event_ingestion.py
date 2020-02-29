"""
Remove GitHub webhook events from Redis and store them in Postgres for analysis.

This script should run constantly.

The web api uses webhook events to calculate and  display metrics about kodiak
activity and determine usage. The Kodiak GitHub Bot accepts GitHub webhooks and
forwards a selection of event types that we care about. The Redis queue is
bounded at 10000 items, so if we have time to recover from downtime/restarts.
"""

import json
import logging
import os
import sys
import time
from typing import NoReturn

import redis
import zstandard as zstd

from core.models import GitHubEvent

logger = logging.getLogger(__name__)

# events that we want to store in Postgres. Discard anything else.
INTERESTING_EVENTS = {"pull_request", "pull_request_review", "pull_request_comment"}


def ingest_events() -> NoReturn:
    """
    Pull webhook events off the queue and insert them into Postgres to calculate
    usage statistics.
    """
    r = redis.Redis.from_url(os.environ["REDIS_URL"])
    try:
        while True:
            logger.info("block for event")

            res = r.blpop("kodiak:webhook_event")
            if res is None:
                logger.info("no event found")
                continue
            _, event_compressed = res

            logger.info("process event")
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(event_compressed)
            event = json.loads(decompressed)

            event_name = event["event_name"]
            if event_name in INTERESTING_EVENTS:
                payload = event["payload"]
                GitHubEvent.objects.create(event_name=event_name, payload=payload)

            time.sleep(0)
    except KeyboardInterrupt:
        pass
