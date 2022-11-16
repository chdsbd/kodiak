"""
Tests for flows that depend on status checks or check_runs.
"""
import pytest

from kodiak.errors import PollForever, RetryForSkippableChecks
from kodiak.queries import StatusState
from kodiak.test_evaluation import (
    CheckConclusionState,
    MergeStateStatus,
    create_api,
    create_branch_protection,
    create_check_run,
    create_config,
    create_context,
    create_mergeable,
    create_pull_request,
)


async def test_mergeable_missing_requires_status_checks_failing_status_context() -> None:
    """
    If branch protection is enabled with requiresStatusChecks but a required check is failing we should not merge.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    context = create_context()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.context = "ci/test-api"
    context.state = StatusState.FAILURE

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
        check_runs=[],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert (
        "failing required status checks: {'ci/test-api'}"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_missing_requires_status_checks_failing_check_run() -> None:
    """
    If branch protection is enabled with requiresStatusChecks but a required check is failing we should not merge.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    for index, check_run_conclusion in enumerate(
        (
            CheckConclusionState.ACTION_REQUIRED,
            CheckConclusionState.FAILURE,
            CheckConclusionState.TIMED_OUT,
            CheckConclusionState.CANCELLED,
            CheckConclusionState.SKIPPED,
            CheckConclusionState.STALE,
        )
    ):
        check_run.conclusion = check_run_conclusion
        await mergeable(
            api=api,
            pull_request=pull_request,
            branch_protection=branch_protection,
            check_runs=[check_run],
            contexts=[],
        )
        assert api.set_status.call_count == 1 + index
        assert api.dequeue.call_count == 1 + index
        assert (
            "failing required status checks: {'ci/test-api'}"
            in api.set_status.calls[index]["msg"]
        )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_travis_ci_checks() -> None:
    """
    GitHub has some weird, _undocumented_ logic for continuous-integration/travis-ci where "continuous-integration/travis-ci/{pr,push}" become "continuous-integration/travis-ci" in requiredStatusChecks.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    context = create_context()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["continuous-integration/travis-ci"]
    context.state = StatusState.FAILURE
    context.context = "continuous-integration/travis-ci/pr"

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
        check_runs=[],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert (
        "failing required status checks: {'continuous-integration/travis-ci/pr'}"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_travis_ci_checks_success() -> None:
    """
    If continuous-integration/travis-ci/pr passes we shouldn't say we're waiting for continuous-integration/travis-ci.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    context = create_context()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = [
        "continuous-integration/travis-ci",
        "ci/test-api",
    ]
    context.state = StatusState.SUCCESS
    context.context = "continuous-integration/travis-ci/pr"

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            pull_request=pull_request,
            branch_protection=branch_protection,
            contexts=[context],
            merging=True,
            check_runs=[],
        )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert (
        "merging PR (waiting for status checks: {'ci/test-api'})"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_skippable_contexts_with_status_check() -> None:
    """
    If a skippable check hasn't finished, we shouldn't do anything.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["WIP", "ci/test-api"]
    config.merge.dont_wait_on_status_checks = ["WIP"]
    context.state = StatusState.PENDING
    context.context = "WIP"
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.SUCCESS

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
        contexts=[context],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert (
        "not waiting for dont_wait_on_status_checks: ['WIP']"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_skippable_contexts_with_check_run() -> None:
    """
    If a skippable check hasn't finished, we shouldn't do anything.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["WIP", "ci/test-api"]
    config.merge.dont_wait_on_status_checks = ["WIP"]
    context.state = StatusState.SUCCESS
    context.context = "ci/test-api"
    check_run.name = "WIP"
    check_run.conclusion = None

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
        contexts=[context],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert (
        "not waiting for dont_wait_on_status_checks: ['WIP']"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_skippable_contexts_passing() -> None:
    """
    If a skippable check is passing we should queue the PR for merging
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["WIP", "ci/test-api"]
    config.merge.dont_wait_on_status_checks = ["WIP"]
    context.state = StatusState.SUCCESS
    context.context = "WIP"
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.SUCCESS

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
        contexts=[context],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False


async def test_mergeable_skippable_contexts_merging_pull_request() -> None:
    """
    If a skippable check hasn't finished but we're merging, we need to raise an exception to retry for a short period of time to allow the check to finish. We won't retry forever because skippable checks will likely never finish.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["WIP", "ci/test-api"]
    config.merge.dont_wait_on_status_checks = ["WIP"]
    context.state = StatusState.PENDING
    context.context = "WIP"
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.SUCCESS

    with pytest.raises(RetryForSkippableChecks):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            check_runs=[check_run],
            contexts=[context],
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert (
        "merging PR (waiting a bit for dont_wait_on_status_checks: ['WIP'])"
        in api.set_status.calls[0]["msg"]
    )
    assert api.dequeue.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_skippable_check_timeout() -> None:
    """
    we wait for skippable checks when merging because it takes time for check statuses to be sent and acknowledged by GitHub. We time out after some time because skippable checks are likely to never complete. In this case we want to notify the user of this via status check.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()
    check_run = create_check_run()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["WIP", "ci/test-api"]
    config.merge.dont_wait_on_status_checks = ["WIP"]
    context.state = StatusState.PENDING
    context.context = "WIP"
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.SUCCESS

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
        check_runs=[check_run],
        merging=True,
        skippable_check_timeout=0,
    )

    assert api.set_status.called is True
    assert (
        "timeout reached for dont_wait_on_status_checks: ['WIP']"
        in api.set_status.calls[0]["msg"]
    )
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


async def test_mergeable_update_always() -> None:
    """
    Kodiak should update PR even when failing requirements for merge
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    check_run = create_check_run()

    config.update.always = True
    config.update.require_automerge_label = True

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
    )
    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


async def test_mergeable_update_autoupdate_label() -> None:
    """
    Kodiak should update the PR when the autoupdate_label is set on the PR.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    check_run = create_check_run()

    config.update.autoupdate_label = "update me please!"

    # create a pull requests that's behind and failing checks. We should still
    # update on failing checks.
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
    )
    assert (
        api.update_branch.call_count == 0
    ), "we shouldn't update when update.autoupdate_label isn't available on the PR"

    # PR should be updated when set on the PR
    pull_request.labels = [config.update.autoupdate_label]
    api = create_api()
    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
    )

    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


async def test_mergeable_update_always_require_automerge_label_missing_label() -> None:
    """
    Kodiak should not update branch if update.require_automerge_label is True and we're missing the automerge label.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    check_run = create_check_run()

    config.update.always = True
    config.update.require_automerge_label = True

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    pull_request.labels = []

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
    )
    assert api.update_branch.call_count == 0

    assert api.set_status.call_count == 1
    assert "Ignored (no automerge label:" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0


async def test_mergeable_update_always_no_require_automerge_label_missing_label() -> None:
    """
    Kodiak should update branch if update.require_automerge_label is True and we're missing the automerge label.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    check_run = create_check_run()

    config.update.always = True
    config.update.require_automerge_label = False

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    pull_request.labels = []

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[check_run],
    )
    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


async def test_duplicate_check_suites() -> None:
    """
    Kodiak should only consider the most recent check run when evaluating a PR
    for merging.

    Regression test.
    """
    api = create_api()
    pull_request = create_pull_request()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection = create_branch_protection()
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["Pre-merge checks"]
    mergeable = create_mergeable()
    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        check_runs=[
            create_check_run(
                name="Pre-merge checks", conclusion=CheckConclusionState.NEUTRAL
            ),
            create_check_run(
                name="Pre-merge checks", conclusion=CheckConclusionState.FAILURE
            ),
            create_check_run(
                name="Pre-merge checks", conclusion=CheckConclusionState.SUCCESS
            ),
        ],
    )
    assert "enqueued for merge" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1


async def test_neutral_required_check_runs() -> None:
    """
    When merge.block_on_neutral_required_check_runs is enabled, we should block
    merge if a required check run has a neutral conclusion.
    """
    api = create_api()
    config = create_config()
    config.merge.block_on_neutral_required_check_runs = True
    branch_protection = create_branch_protection()
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["Pre-merge checks"]

    mergeable = create_mergeable()
    await mergeable(
        api=api,
        branch_protection=branch_protection,
        config=config,
        check_runs=[
            create_check_run(
                name="Pre-merge checks", conclusion=CheckConclusionState.NEUTRAL
            ),
        ],
    )
    assert "neutral required check runs" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 1
