from __future__ import annotations

import json
from collections import defaultdict
from typing import List, NamedTuple

import pydantic
import redis
from django.conf import settings

r = redis.Redis.from_url(settings.REDIS_URL)


class KodiakQueueEntry(pydantic.BaseModel):
    """
    must match schema from bot: https://github.com/chdsbd/kodiak/blob/4d4c2a31b6ceb2136f83281a154f47e8b49a86ac/bot/kodiak/queue.py#L30-L35
    """

    pull_request_number: str


class PullRequest(pydantic.BaseModel):
    number: str
    added_at_timestamp: float


class Queue(pydantic.BaseModel):
    branch: str
    pull_requests: List[PullRequest]


class Repository(pydantic.BaseModel):
    repo: str
    owner: str
    queues: List[Queue]


class RepositoryName(NamedTuple):
    owner: str
    repo: str


def get_active_merge_queues(*, install_id: str) -> List[Queue]:
    count, keys = r.scan(cursor=0, match=f"merge_queue:{install_id}*", count=50)

    merge_queues = [key for key in keys if not key.endswith(b":target")]
    pipe = r.pipeline(transaction=False)
    for queue in merge_queues:
        pipe.zrange(queue, 0, 1000, withscores=True)
    res = pipe.execute()

    queues = defaultdict(list)
    for queue_name, entries in zip(merge_queues, res):
        queue_name = queue_name.decode()
        org, repo, branch = queue_name.split(".")[1].split("/")
        pull_requests = sorted(
            [
                PullRequest(
                    number=KodiakQueueEntry.parse_raw(pull_request).pull_request_number,
                    added_at_timestamp=score,
                )
                for pull_request, score in entries
            ],
            key=lambda x: x.added_at_timestamp,
        )
        queues[RepositoryName(owner=org, repo=repo)].append(
            Queue(branch=branch, pull_requests=pull_requests)
        )
    return queues
