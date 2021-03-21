from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Mapping, NamedTuple, Optional, Set, TypeVar

import pydantic
import redis
from django.conf import settings

log = logging.getLogger(__name__)

r = redis.Redis.from_url(settings.REDIS_URL)


class KodiakQueueEntry(pydantic.BaseModel):
    """
    must match schema from bot:
    https://github.com/chdsbd/kodiak/blob/4d4c2a31b6ceb2136f83281a154f47e8b49a86ac/bot/kodiak/queue.py#L30-L35
    """

    pull_request_number: str


class PullRequest(pydantic.BaseModel):
    number: str
    merging: bool = False
    added_at_timestamp: Optional[float]


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


def queue_to_target(queue: bytes) -> bytes:
    return queue + b":target"


def parse_kodiak_queue_entry(data: bytes) -> KodiakQueueEntry | None:
    try:
        return KodiakQueueEntry.parse_raw(data)
    except pydantic.ValidationError:
        log.exception("failed to parse pull request")
    return None


def get_active_merge_queues(*, install_id: str) -> Mapping[RepositoryName, List[Queue]]:
    queue_names: Set[bytes] = r.smembers(f"merge_queue_by_install:{install_id}")  # type: ignore [assignment]
    pipe = r.pipeline(transaction=False)
    for queue in queue_names:
        pipe.get(queue_to_target(queue))
        pipe.get(queue_to_target(queue) + b":time")
        pipe.zrange(queue, 0, 1000, withscores=True)  # type: ignore [no-untyped-call]
    # response is a list[bytes | None, bytes | None, list[tuple[bytes, float]], ...]
    res = pipe.execute()

    it = iter(res)
    queues = defaultdict(list)
    for queue, (merging_pr_raw, current_pr_added_at, waiting_prs) in zip(
        queue_names, zip(it, it, it)
    ):
        org, repo, branch = queue_info_from_name(queue.decode())

        pull_requests = []
        merging_pr = (
            parse_kodiak_queue_entry(merging_pr_raw) if merging_pr_raw else None
        )
        if merging_pr:
            pull_requests.append(
                PullRequest(
                    number=merging_pr.pull_request_number,
                    merging=True,
                    added_at_timestamp=float(current_pr_added_at)
                    if current_pr_added_at
                    else None,
                )
            )
        for pull_request, score in waiting_prs:
            pr = parse_kodiak_queue_entry(pull_request)
            if not pr:
                continue
            # current_pr can existing in waiting_prs too. We only want to show
            # it once.
            if merging_pr and pr.pull_request_number == merging_pr.pull_request_number:
                continue
            pull_requests.append(
                PullRequest(number=pr.pull_request_number, added_at_timestamp=score,)
            )

        pull_requests = sorted(pull_requests, key=lambda x: x.added_at_timestamp or 0)
        # only add report targets that have pull requests merging or in queue.
        if pull_requests:
            queues[RepositoryName(owner=org, repo=repo)].append(
                Queue(branch=branch, pull_requests=pull_requests)
            )

    return queues
