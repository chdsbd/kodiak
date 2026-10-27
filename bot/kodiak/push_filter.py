"""
Decide which pull requests a push to their base branch can affect.

A push to a base branch can make its pull requests out of date, so we evaluate
them in case Kodiak should update or merge them. Most pull requests in busy
repositories aren't ones Kodiak acts on (no automerge label), and evaluating
them only reaches the "Ignored" status again.

We don't have the repository's config when handling a push, so we cache the
fields we need whenever we evaluate a pull request.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable, List, Optional

import pydantic

from kodiak.config import V1
from kodiak.queries import CONFIG_FILE_NAME
from kodiak.redis_client import redis_bot

CACHE_TTL = timedelta(hours=1)

CONFIG_FILE_PATHS = {CONFIG_FILE_NAME, f".github/{CONFIG_FILE_NAME}"}


class PushFilterConfig(pydantic.BaseModel):
    automerge_labels: List[str]
    require_automerge_label: bool
    automerge_dependency_usernames: List[str]
    update_always: bool
    update_require_automerge_label: bool
    autoupdate_label: Optional[str]

    @classmethod
    def from_config(cls, config: V1) -> PushFilterConfig:
        automerge_label = config.merge.automerge_label
        return cls(
            automerge_labels=(
                [automerge_label]
                if isinstance(automerge_label, str)
                else list(automerge_label)
            ),
            require_automerge_label=config.merge.require_automerge_label,
            automerge_dependency_usernames=config.merge.automerge_dependencies.usernames,
            update_always=config.update.always,
            update_require_automerge_label=config.update.require_automerge_label,
            autoupdate_label=config.update.autoupdate_label,
        )

    def may_act_on(self, *, labels: Iterable[str], author: Optional[str]) -> bool:
        """
        Whether Kodiak may update or merge a pull request with these labels.

        This mirrors the checks in `mergeable` for which pull requests need a
        mergeability check. For dependency automerge we only check the author,
        which errs toward evaluating the pull request.
        """
        labels = set(labels)
        has_automerge_label = not labels.isdisjoint(self.automerge_labels)
        return (
            has_automerge_label
            or not self.require_automerge_label
            or (author is not None and author in self.automerge_dependency_usernames)
            or (
                self.update_always
                and (has_automerge_label or not self.update_require_automerge_label)
            )
            or (self.autoupdate_label is not None and self.autoupdate_label in labels)
        )


def get_cache_key(*, installation_id: str, owner: str, repo: str) -> str:
    return f"kodiak:push_filter_config:{installation_id}.{owner}/{repo}"


async def save_push_filter_config(
    *, installation_id: str, owner: str, repo: str, config: V1
) -> None:
    await redis_bot.set(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo),
        PushFilterConfig.from_config(config).json(),
        ex=CACHE_TTL,
    )


async def get_push_filter_config(
    *, installation_id: str, owner: str, repo: str
) -> Optional[PushFilterConfig]:
    """
    Returns None if we haven't evaluated a pull request in the repository
    recently, in which case every pull request should be evaluated.
    """
    cached = await redis_bot.get(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo)
    )
    if cached is None:
        return None
    return PushFilterConfig.parse_raw(cached)


async def forget_push_filter_config(
    *, installation_id: str, owner: str, repo: str
) -> None:
    await redis_bot.delete(
        get_cache_key(installation_id=installation_id, owner=owner, repo=repo)
    )
