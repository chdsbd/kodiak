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
import time

import redis
import zstandard as zstd

from core.models import GitHubEvent
from core.utils import GracefulTermination

logger = logging.getLogger(__name__)

# events that we want to store in Postgres. Discard anything else.
INTERESTING_EVENTS = {"pull_request", "pull_request_review", "pull_request_comment"}


def ingest_events() -> None:
    """
    Pull webhook events off the queue and insert them into Postgres to calculate
    usage statistics.
    """
    r = redis.Redis.from_url(os.environ["REDIS_URL"])
    while True:
        time.sleep(0)
        # we don't want to lose events when we terminate the process, so we
        # handle SIGINT and SIGTERM gracefully. We use a short timeout of Redis
        # BLPOP so we don't have to wait too long.
        with GracefulTermination():
            logger.info("block for event")
            res = r.blpop("kodiak:webhook_event", timeout=5)
            if res is None:
                # if res is None we likely hit the timeout.
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
