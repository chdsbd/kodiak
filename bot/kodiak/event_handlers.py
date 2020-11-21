from __future__ import annotations

import asyncio
import json
from typing import List, Optional, Set, cast

import asyncio_redis
import structlog
import zstandard as zstd

from kodiak import app_config as conf
from kodiak import queries
from kodiak.events import (
    CheckRunEvent,
    PullRequestEvent,
    PullRequestReviewEvent,
    PushEvent,
    StatusEvent,
)
from kodiak.events.status import Branch
from kodiak.queries import Client, GetOpenPullRequestsResponse
from kodiak.queue import WebhookEvent, redis_webhook_queue

logger = structlog.get_logger()


async def pr_event(pr: PullRequestEvent) -> None:
    """
    Trigger evaluation of modified PR.
    """
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=pr.repository.owner.login,
            repo_name=pr.repository.name,
            pull_request_number=pr.number,
            installation_id=str(pr.installation.id),
        )
    )


async def check_run(check_run_event: CheckRunEvent) -> None:
    """
    Trigger evaluation of all PRs included in check run.
    """
    # Prevent an infinite loop when we update our check run
    if check_run_event.check_run.name == queries.CHECK_RUN_NAME:
        return
    for pr in check_run_event.check_run.pull_requests:
        await redis_webhook_queue.enqueue(
            event=WebhookEvent(
                repo_owner=check_run_event.repository.owner.login,
                repo_name=check_run_event.repository.name,
                pull_request_number=pr.number,
                installation_id=str(check_run_event.installation.id),
            )
        )


def find_branch_names_latest(sha: str, branches: List[Branch]) -> List[str]:
    """
    from the docs:
        The "branches" key is "an array of branch objects containing the status'
        SHA. Each branch contains the given SHA, but the SHA may or may not be
        the head of the branch. The array includes a maximum of 10 branches.""
    https://developer.github.com/v3/activity/events/types/#statusevent

    NOTE(chdsbd): only take branches with commit at branch head to reduce
    potential number of api requests we need to make.
    """
    return [branch.name for branch in branches if branch.commit.sha == sha]


async def status_event(status_event: StatusEvent) -> None:
    """
    Trigger evaluation of all PRs associated with the status event commit SHA.
    """
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    log = logger.bind(owner=owner, repo=repo, install=installation_id)

    refs = find_branch_names_latest(
        sha=status_event.sha, branches=status_event.branches
    )

    async with Client(
        owner=owner, repo=repo, installation_id=installation_id
    ) as api_client:
        if len(refs) == 0:
            # when a pull request is from a fork the status event will not have
            # any `branches`, so to be able to trigger evaluation of the PR, we
            # fetch all pull requests.
            #
            # I think we could optimize this by selecting only the fork PRs, but
            # I worry that we might miss some events where `branches` is empty,
            # but not because of a fork.
            pr_results = [await api_client.get_open_pull_requests()]
            log.info("could not find refs for status_event")
        else:
            pr_requests = [
                api_client.get_open_pull_requests(head=f"{owner}:{ref}") for ref in refs
            ]
            pr_results = cast(
                List[Optional[List[GetOpenPullRequestsResponse]]],
                await asyncio.gather(*pr_requests),
            )

        all_events: Set[WebhookEvent] = set()
        for prs in pr_results:
            if prs is None:
                continue
            for pr in prs:
                all_events.add(
                    WebhookEvent(
                        repo_owner=owner,
                        repo_name=repo,
                        pull_request_number=pr.number,
                        installation_id=str(installation_id),
                    )
                )
        for event in all_events:
            await redis_webhook_queue.enqueue(event=event)


async def pr_review(review: PullRequestReviewEvent) -> None:
    """
    Trigger evaluation of the modified PR.
    """
    await redis_webhook_queue.enqueue(
        event=WebhookEvent(
            repo_owner=review.repository.owner.login,
            repo_name=review.repository.name,
            pull_request_number=review.pull_request.number,
            installation_id=str(review.installation.id),
        )
    )


def get_branch_name(raw_ref: str) -> Optional[str]:
    """
    Extract the branch name from the ref
    """
    if raw_ref.startswith("refs/heads/"):
        return raw_ref.split("refs/heads/", 1)[1]
    return None


async def push(push_event: PushEvent) -> None:
    """
    Trigger evaluation of PRs that depend on the pushed branch.
    """
    owner = push_event.repository.owner.login
    repo = push_event.repository.name
    installation_id = str(push_event.installation.id)
    branch_name = get_branch_name(push_event.ref)
    log = logger.bind(ref=push_event.ref, branch_name=branch_name)
    if branch_name is None:
        log.info("could not extract branch name from ref")
        return
    async with Client(
        owner=owner, repo=repo, installation_id=installation_id
    ) as api_client:
        # find all the PRs that depend on the branch affected by this push and
        # queue them for evaluation.
        # Any PR that has a base ref matching our event ref is dependent.
        prs = await api_client.get_open_pull_requests(base=branch_name)
        if prs is None:
            log.info("api call to find pull requests failed")
            return None
        for pr in prs:
            await redis_webhook_queue.enqueue(
                event=WebhookEvent(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    installation_id=installation_id,
                )
            )


_redis = None


async def get_redis() -> asyncio_redis.Connection:
    global _redis  # pylint: disable=global-statement
    if _redis is None:
        _redis = await asyncio_redis.Pool.create(
            host=conf.REDIS_URL.hostname or "localhost",
            port=conf.REDIS_URL.port or 6379,
            password=(
                conf.REDIS_URL.password.encode() if conf.REDIS_URL.password else None
            ),
            poolsize=conf.USAGE_REPORTING_POOL_SIZE,
            encoder=asyncio_redis.encoders.BytesEncoder(),
        )
    return _redis


def compress_payload(data: dict) -> bytes:
    cctx = zstd.ZstdCompressor()
    return cctx.compress(json.dumps(data).encode())


async def handle_webhook_event(event_name: str, payload: dict) -> None:
    log = logger.bind(event_name=event_name)

    if conf.USAGE_REPORTING and event_name in conf.USAGE_REPORTING_EVENTS:
        # store events in Redis for dequeue by web api job.
        #
        # We limit the queue length to ensure that if the dequeue job fails, we
        # won't overload Redis.
        redis = await get_redis()
        await redis.rpush(
            b"kodiak:webhook_event",
            [compress_payload(dict(event_name=event_name, payload=payload))],
        )
        await redis.ltrim(b"kodiak:webhook_event", 0, conf.USAGE_REPORTING_QUEUE_LENGTH)
        log = log.bind(usage_reported=True)

    if event_name == "check_run":
        await check_run(CheckRunEvent.parse_obj(payload))
    elif event_name == "pull_request":
        await pr_event(PullRequestEvent.parse_obj(payload))
    elif event_name == "pull_request_review":
        await pr_review(PullRequestReviewEvent.parse_obj(payload))
    elif event_name == "push":
        await push(PushEvent.parse_obj(payload))
    elif event_name == "status":
        await status_event(StatusEvent.parse_obj(payload))
    else:
        log = log.bind(event_parsed=False)

    log.info("webhook_event_handled")
