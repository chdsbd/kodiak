"""
Decide which pull requests a push to their base branch can affect.

A push to a base branch can make its pull requests out of date, so we evaluate
them in case Kodiak should update or merge them. Most pull requests in busy
repositories aren't ones Kodiak acts on (no automerge label), and evaluating
them only reaches the "Ignored" status again.

We don't have the repository's config when handling a push, so we cache the
config whenever we evaluate a pull request.

Check run events don't include a pull request's labels either, so we also
remember which pull requests Kodiak can't act on when we evaluate them. Label
and review events aren't filtered, so they still refresh what we remember.

Builds report dozens of statuses for each commit, so we briefly remember which
open pull requests are at a commit too.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List, Optional

import pydantic

from kodiak.config import V1
from kodiak.evaluation import may_update_or_merge
from kodiak.queries import CONFIG_FILE_NAME
from kodiak.redis_client import redis_bot

CACHE_TTL = timedelta(hours=1)

CONFIG_FILE_PATHS = {CONFIG_FILE_NAME, f".github/{CONFIG_FILE_NAME}"}


def may_act_on(config: V1, *, labels: Iterable[str], author: Optional[str]) -> bool:
    """
    Whether Kodiak may update or merge a pull request in the push's base branch.

    The pull request list doesn't include the dependency version, so for
    dependency automerge we only check the author, which errs toward
    evaluating the pull request.
    """
    return may_update_or_merge(
        config,
        labels=labels,
        dependency_automerge=(
            author is not None
            and author in config.merge.automerge_dependencies.usernames
        ),
    )


def get_cache_key(*, installation_id: str, owner: str, repo: str) -> str:
    return f"kodiak:push_filter_config:{installation_id}.{owner}/{repo}"


async def save_push_filter_config(
    *, installation_id: str, owner: str, repo: str, config: V1
) -> None:
    await redis_bot.set(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo),
        config.json(),
        ex=CACHE_TTL,
    )


async def get_push_filter_config(
    *, installation_id: str, owner: str, repo: str
) -> Optional[V1]:
    """
    Returns None if we haven't evaluated a pull request in the repository
    recently, in which case every pull request should be evaluated.
    """
    cached = await redis_bot.get(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo)
    )
    if cached is None:
        return None
    return V1.parse_raw(cached)


async def forget_push_filter_config(
    *, installation_id: str, owner: str, repo: str
) -> None:
    await redis_bot.delete(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo)
    )


def get_ignored_pull_request_key(
    *, installation_id: str, owner: str, repo: str, number: int
) -> str:
    return f"kodiak:ignored_pull_request:{installation_id}.{owner}/{repo}#{number}"


async def save_pull_request_ignored(
    *, installation_id: str, owner: str, repo: str, number: int, ignored: bool
) -> None:
    key = get_ignored_pull_request_key(
        installation_id=installation_id, owner=owner, repo=repo, number=number
    )
    if ignored:
        await redis_bot.set(key, b"1", ex=CACHE_TTL)
    else:
        await redis_bot.delete(key)


async def is_pull_request_ignored(
    *, installation_id: str, owner: str, repo: str, number: int
) -> bool:
    """
    Returns False if we haven't evaluated the pull request recently, in which
    case it should be evaluated.
    """
    return bool(
        await redis_bot.exists(
            get_ignored_pull_request_key(
                installation_id=installation_id, owner=owner, repo=repo, number=number
            )
        )
    )


# builds report dozens of statuses for each commit, often within seconds, and
# keep reporting them after its pull request merges or its branch moves on. We
# remember which open pull requests are at a commit briefly so we look them up
# once. Pull request events forget the commit, since a pull request opened at
# it would otherwise be missed.
STATUS_COMMIT_TTL = timedelta(minutes=5)


class StatusCommitPullRequest(pydantic.BaseModel):
    number: int
    base_ref: str


class StatusCommitPullRequests(pydantic.BaseModel):
    pull_requests: List[StatusCommitPullRequest]


def get_status_commit_key(
    *, installation_id: str, owner: str, repo: str, sha: str
) -> str:
    return f"kodiak:status_commit_pull_requests:{installation_id}.{owner}/{repo}:{sha}"


async def save_status_commit_pull_requests(
    *,
    installation_id: str,
    owner: str,
    repo: str,
    sha: str,
    pull_requests: List[StatusCommitPullRequest],
) -> None:
    await redis_bot.set(
        get_status_commit_key(
            installation_id=installation_id, owner=owner, repo=repo, sha=sha
        ),
        StatusCommitPullRequests(pull_requests=pull_requests).json(),
        ex=STATUS_COMMIT_TTL,
    )


async def get_status_commit_pull_requests(
    *, installation_id: str, owner: str, repo: str, sha: str
) -> Optional[List[StatusCommitPullRequest]]:
    """
    The open pull requests we recently found at this commit, or None if we
    haven't looked them up.
    """
    cached = await redis_bot.get(
        get_status_commit_key(
            installation_id=installation_id, owner=owner, repo=repo, sha=sha
        )
    )
    if cached is None:
        return None
    return StatusCommitPullRequests.parse_raw(cached).pull_requests


async def forget_status_commit(
    *, installation_id: str, owner: str, repo: str, sha: str
) -> None:
    await redis_bot.delete(
        get_status_commit_key(
            installation_id=installation_id, owner=owner, repo=repo, sha=sha
        )
    )
