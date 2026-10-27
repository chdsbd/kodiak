from __future__ import annotations

from typing import List, Optional

import pytest

from kodiak.config import V1, AutomergeDependencies, Merge, Update
from kodiak.push_filter import may_act_on as push_may_act_on


def may_act_on(
    config: V1, *, labels: List[str], author: Optional[str] = "octocat"
) -> bool:
    return push_may_act_on(config, labels=labels, author=author)


def test_default_config_ignores_unlabeled_pull_requests() -> None:
    config = V1(version=1)

    assert may_act_on(config, labels=["automerge"])
    assert not may_act_on(config, labels=["bug"])


@pytest.mark.parametrize(
    "config, labels, author",
    (
        pytest.param(
            V1(version=1, merge=Merge(automerge_label=["ship-it", "automerge"])),
            ["ship-it"],
            "octocat",
            id="any automerge label",
        ),
        pytest.param(
            V1(version=1, merge=Merge(require_automerge_label=False)),
            [],
            "octocat",
            id="automerge label not required",
        ),
        pytest.param(
            V1(version=1, update=Update(always=True, require_automerge_label=False)),
            [],
            "octocat",
            id="update.always without label",
        ),
        pytest.param(
            V1(version=1, update=Update(autoupdate_label="autoupdate")),
            ["autoupdate"],
            "octocat",
            id="autoupdate label",
        ),
        pytest.param(
            V1(
                version=1,
                merge=Merge(
                    automerge_dependencies=AutomergeDependencies(
                        usernames=["dependabot"], versions=["minor"]
                    )
                ),
            ),
            [],
            "dependabot",
            id="dependency automerge author",
        ),
    ),
)
def test_pull_requests_kodiak_may_act_on(
    config: V1, labels: List[str], author: str
) -> None:
    assert may_act_on(config, labels=labels, author=author)


def test_update_always_still_requires_label_by_default() -> None:
    """
    `update.always` only applies to labeled pull requests unless
    `update.require_automerge_label` is disabled.
    """
    config = V1(version=1, update=Update(always=True))

    assert not may_act_on(config, labels=[])
