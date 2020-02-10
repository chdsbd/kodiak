import redis
import zstandard as zstd
import json
import time
import django
import logging
import sys

django.setup()
# must setup django before importing models
from core.models import GitHubEvent

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# events that we want to store in Postgres. Discard anything else.
INTERESTING_EVENTS = {"pull_request", "pull_request_review", "pull_request_comment"}


def main():
    """
    Pull webhook events off the queue and insert them into Postgres to calculate
    usage statistics.
    """
    r = redis.Redis()
    while True:
        logger.info("block for event")

        _, event_compressed = r.blpop("kodiak:webhook_event")

        logger.info("process event")
        dctx = zstd.ZstdDecompressor()
        decompressed = dctx.decompress(event_compressed)
        event = json.loads(decompressed)

        event_name = event["event_name"]
        if event_name in INTERESTING_EVENTS:
            payload = event["payload"]
            GitHubEvent.objects.create(event_name=event_name, payload=payload)

        time.sleep(0)


if __name__ == "__main__":
    main()
