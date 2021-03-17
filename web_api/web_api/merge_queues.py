from __future__ import annotations

from collections import defaultdict
from typing import List, Mapping, NamedTuple

import pydantic
import redis
from django.conf import settings

r = redis.Redis.from_url(settings.REDIS_URL)


class KodiakQueueEntry(pydantic.BaseModel):
    """
    must match schema from bot:
    https://github.com/chdsbd/kodiak/blob/4d4c2a31b6ceb2136f83281a154f47e8b49a86ac/bot/kodiak/queue.py#L30-L35
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


class QueueInfo(NamedTuple):
    org: str
    repo: str
    branch: str


def queue_info_from_name(name: str) -> QueueInfo:
    """
    Parse queue name like "merge_queue:11256551.sbdchd/squawk/main"
    """
    org, repo, branch = name.split(".", 1)[1].split("/", 2)
    return QueueInfo(org, repo, branch)


def get_active_merge_queues(*, install_id: str) -> Mapping[RepositoryName, List[Queue]]:
    count, keys = r.scan(cursor=0, match=f"merge_queue:{install_id}*", count=50)

    # Remove keys for tracking actively merging pull request.
    #
    # We append ':target' to the merge queue name to track the merging pull request.
    # https://github.com/chdsbd/kodiak/blob/b68608e4622ab149997f0cece4d615c2ac51157f/bot/kodiak/queue.py#L41
    merge_queues = [key for key in keys if not key.endswith(b":target")]
    pipe = r.pipeline(transaction=False)
    for queue in merge_queues:
        pipe.zrange(queue, 0, 1000, withscores=True)  # type: ignore [no-untyped-call]
    res = pipe.execute()

    # we accumulate merge queues by repository.
    queues = defaultdict(list)
    for queue_name, entries in zip(merge_queues, res):
        org, repo, branch = queue_info_from_name(queue_name.decode())
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
