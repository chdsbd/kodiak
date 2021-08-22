import re
from pathlib import Path

import pytest

from kodiak.dependencies import MatchType
from kodiak.test_evaluation import (
    create_api,
    create_config,
    create_mergeable,
    create_pull_request,
)
from kodiak.tests.dependencies.test_dependencies import FakePR, generate_test_cases


@pytest.mark.asyncio
async def test_merge_okay() -> None:
    """
    Happy case.

    The upgrade type (patch) is specified in "versions" and the PR author
    "my-custom-dependabot" is specified in "usernames".
    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.automerge_dependencies.versions = ["minor", "patch"]
    config.merge.automerge_dependencies.usernames = ["my-custom-dependabot"]
    pull_request = create_pull_request()
    pull_request.labels = []
    pull_request.author.login = "my-custom-dependabot"
    pull_request.title = "Bump lodash from 4.17.15 to 4.17.19"
    api = create_api()
    await mergeable(api=api, pull_request=pull_request, config=config)
    assert api.set_status.call_count == 1
    assert "enqueued" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_merge_mismatch_username() -> None:
    """
    We should only merge the pull request if the userrname is specified within
    "usernames" and the version type is in the "versions" field.

    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.automerge_dependencies.versions = ["minor", "patch"]
    config.merge.automerge_dependencies.usernames = ["dependabot"]
    pull_request = create_pull_request()
    pull_request.labels = []
    pull_request.author.login = "my-custom-dependabot"
    pull_request.title = "Bump lodash from 4.17.15 to 4.17.19"
    api = create_api()
    await mergeable(api=api, pull_request=pull_request, config=config)
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 1


@pytest.mark.asyncio
async def test_merge_no_version_found() -> None:
    """
    If we can't find a version from the PR title, we shouldn't merge.

    Packages don't necessarily use semver.
    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.automerge_dependencies.versions = ["minor", "patch"]
    config.merge.automerge_dependencies.usernames = ["my-custom-dependabot"]
    pull_request = create_pull_request()
    pull_request.labels = []
    pull_request.author.login = "my-custom-dependabot"

    for title in ("Bump lodash from 4.17.15 to", "Bump lodash from griffin to phoenix"):
        pull_request.title = title
        api = create_api()
        await mergeable(api=api, pull_request=pull_request, config=config)
        assert api.queue_for_merge.call_count == 0
        assert api.dequeue.call_count == 1


@pytest.mark.asyncio
async def test_merge_disallowed_version() -> None:
    """
    We should only auto merge if the upgrade type is specified in "versions".

    So if a PR is a major upgrade, we should only auto merge if "major" is in
    the "versions" configuration.
    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.automerge_dependencies.versions = ["minor", "patch"]
    config.merge.automerge_dependencies.usernames = ["my-custom-dependabot"]
    pull_request = create_pull_request()
    pull_request.labels = []
    pull_request.author.login = "my-custom-dependabot"
    pull_request.title = "Bump lodash from 4.17.15 to 5.0.1"
    api = create_api()
    await mergeable(api=api, pull_request=pull_request, config=config)
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("pr,update_type", generate_test_cases())
async def test_merge_renovate(pr: FakePR, update_type: MatchType) -> None:
    mergeable = create_mergeable()
    config = create_config()
    config.merge.automerge_dependencies.usernames = ["my-custom-renovate"]
    pull_request = create_pull_request()
    pull_request.labels = []
    pull_request.author.login = "my-custom-renovate"
    pull_request.title = pr.title
    pull_request.body = pr.body

    for version in (update_type, None):
        config.merge.automerge_dependencies.versions = (
            [version] if version is not None else []
        )
        api = create_api()
        await mergeable(api=api, pull_request=pull_request, config=config)
        if version:
            assert api.queue_for_merge.call_count == 1
            assert api.dequeue.call_count == 0
        else:
            assert api.queue_for_merge.call_count == 0
            assert api.dequeue.call_count == 1
