from datetime import datetime, timedelta

import pytest

from kodiak.config import MergeMethod
from kodiak.errors import PollForever
from kodiak.queries import (
    CheckConclusionState,
    MergeStateStatus,
    NodeListPushAllowance,
    Permission,
    PRReview,
    PRReviewAuthor,
    PRReviewState,
    PullRequestReviewDecision,
    PushAllowance,
    PushAllowanceActor,
    ReviewThread,
    StatusState,
)
from kodiak.test_evaluation import (
    create_api,
    create_branch_protection,
    create_check_run,
    create_config,
    create_context,
    create_mergeable,
    create_pull_request,
    create_review,
    create_review_request,
)


@pytest.mark.asyncio
async def test_mergeable_missing_push_allowance() -> None:
    """
    We should warn when user is missing a push allowance with restrictsPushes
    enabled. If Kodiak isn't given an allowance it won't be able to merge pull
    requests and will get a mysterious "merge blocked by GitHub requirements".
    """
    api = create_api()
    mergeable = create_mergeable()
    branch_protection = create_branch_protection()
    branch_protection.restrictsPushes = True
    branch_protection.pushAllowances = NodeListPushAllowance(nodes=[])
    await mergeable(api=api, branch_protection=branch_protection)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "config error" in api.set_status.calls[0]["msg"]
    assert "missing push allowance for Kodiak" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_push_allowance_correct() -> None:
    """
    When restrictsPushes is enabled, but Kodiak is added as a push allowance, we
    should not raise a configuration error. We should let the merge continue
    unimpeded.
    """
    api = create_api()
    mergeable = create_mergeable()
    branch_protection = create_branch_protection()
    branch_protection.restrictsPushes = True
    branch_protection.pushAllowances = NodeListPushAllowance(
        nodes=[PushAllowance(actor=PushAllowanceActor(databaseId=534524))]
    )
    await mergeable(api=api, branch_protection=branch_protection)
    assert api.queue_for_merge.called is True

    assert api.dequeue.call_count == 0
    assert api.update_branch.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_push_allowance_correct_null_database_id() -> None:
    """
    Verify we can handle a null databaseId for the PushAllowanceActor
    """
    api = create_api()
    mergeable = create_mergeable()
    branch_protection = create_branch_protection()
    branch_protection.restrictsPushes = True
    branch_protection.pushAllowances = NodeListPushAllowance(
        nodes=[
            PushAllowance(actor=PushAllowanceActor(databaseId=None)),
            PushAllowance(actor=PushAllowanceActor(databaseId=534524)),
        ]
    )
    await mergeable(api=api, branch_protection=branch_protection)
    assert api.queue_for_merge.called is True

    assert api.dequeue.call_count == 0
    assert api.update_branch.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_push_allowance_merge_do_not_merge() -> None:
    """
    When merge.do_not_merge is enabled, we should ignore any issues with restrictPushes because Kodiak isn't pushing.
    """
    api = create_api()
    mergeable = create_mergeable()
    branch_protection = create_branch_protection()
    config = create_config()

    branch_protection.restrictsPushes = True
    config.merge.do_not_merge = True
    branch_protection.pushAllowances = NodeListPushAllowance(nodes=[])
    await mergeable(api=api, config=config, branch_protection=branch_protection)

    assert api.set_status.call_count == 1
    assert api.set_status.calls[0]["msg"] == "✅ okay to merge"

    assert api.queue_for_merge.called is False
    assert api.dequeue.call_count == 0
    assert api.update_branch.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_requires_commit_signatures_rebase() -> None:
    """
    requiresCommitSignatures doesn't work with Kodiak when rebase is configured
    
    https://github.com/chdsbd/kodiak/issues/89
    """
    api = create_api()
    mergeable = create_mergeable()
    branch_protection = create_branch_protection()
    config = create_config()

    branch_protection.requiresCommitSignatures = True
    config.merge.method = MergeMethod.rebase
    await mergeable(
        api=api,
        config=config,
        branch_protection=branch_protection,
        valid_merge_methods=[MergeMethod.rebase],
    )
    assert (
        '"Require signed commits" branch protection is only supported'
        in api.set_status.calls[0]["msg"]
    )

    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_requires_commit_signatures_squash_and_merge() -> None:
    """
    requiresCommitSignatures works with merge commits and squash
    
    https://github.com/chdsbd/kodiak/issues/89
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    branch_protection = create_branch_protection()

    branch_protection.requiresCommitSignatures = True
    for index, method in enumerate((MergeMethod.squash, MergeMethod.merge)):
        config.merge.method = method
        await mergeable(
            api=api,
            config=config,
            branch_protection=branch_protection,
            valid_merge_methods=[method],
        )
        assert api.set_status.call_count == index + 1
        assert "enqueued for merge" in api.set_status.calls[index]["msg"]
        assert api.queue_for_merge.call_count == index + 1
        assert api.dequeue.call_count == 0

        # verify we haven't tried to update/merge the PR
        assert api.update_branch.called is False
        assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews() -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't
    have enought approving reviews.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_has_review_with_missing_perms() -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't have enough reviews. If a reviewer doesn't have permissions we should ignore their review.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review = create_review()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.READ

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_changes_requested() -> None:
    """
    Don't merge when branch protection requires approving reviews and a user requested changes.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review = create_review()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    review.state = PRReviewState.CHANGES_REQUESTED
    review.author.permission = Permission.WRITE

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "changes requested by 'ghost'" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_missing_approving_review_count() -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't have enough.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review = create_review()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 2
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.WRITE

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews, have 1/2" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_code_owners() -> None:
    """
    Don't merge when code owners are required for review.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review = create_review()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    pull_request.reviewDecision = PullRequestReviewDecision.REVIEW_REQUIRED
    # previously with code owner blocked PRs Kodiak would update the pull
    # request, even if the pull request was blocked from merging.
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND

    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    branch_protection.requiresCodeOwnerReviews = True
    # this pull request meets requiredApprovingReviewCount, but is missing a
    # code owner approval.
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.WRITE

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required review" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_update_branch_immediately() -> None:
    """
    update branch immediately if configured
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    config.merge.update_branch_immediately = True

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_update_branch_immediately_mode_merging() -> None:
    """
    update branch immediately if configured. When we are merging we should raise the PollForever exception to keep the merge loop going instead of returning.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    config.merge.update_branch_immediately = True

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_optimistic_update_need_branch_update() -> None:
    """
    prioritize branch update over waiting for checks when merging if merge.optimistic_updates enabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()

    config.merge.optimistic_updates = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.state = StatusState.PENDING
    context.context = "ci/test-api"

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            contexts=[context],
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_need_branch_update() -> None:
    """
    prioritize waiting for checks over branch updates when merging if merge.optimistic_updates is disabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()

    config.merge.optimistic_updates = False
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.state = StatusState.PENDING
    context.context = "ci/test-api"

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            contexts=[context],
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert (
        "merging PR (waiting for status checks: {'ci/test-api'})"
        in api.set_status.calls[0]["msg"]
    )
    assert api.dequeue.call_count == 0

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_queue_in_progress() -> None:
    """
    If a PR has pending status checks or is behind, we still consider it eligible for merge and throw it in the merge queue.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()

    config.merge.optimistic_updates = False
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.state = StatusState.PENDING
    context.context = "ci/test-api"

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_queue_in_progress_with_ready_to_merge() -> None:
    """
    If a PR has pending status checks or is behind, we still consider it eligible for merge and throw it in the merge queue.

    regression test to verify that with config.merge.prioritize_ready_to_merge =
    true we don't attempt to merge a PR directly but called queue_for_merge
    instead. If the status checks haven't passed or the branch needs an update
    it's not good to be merged directly, but it can be queued for the merge
    queue.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config = create_config()
    context = create_context()

    config.merge.optimistic_updates = False
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.state = StatusState.PENDING
    context.context = "ci/test-api"
    config.merge.prioritize_ready_to_merge = True

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_optimistic_update_wait_for_checks() -> None:
    """
    test merge.optimistic_updates when we don't need a branch update. Since merge.optimistic_updates is enabled we should wait_for_checks
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    context = create_context()

    config.merge.optimistic_updates = True
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresStrictStatusChecks = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.state = StatusState.PENDING
    context.context = "ci/test-api"

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            contexts=[context],
            #
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert (
        "merging PR (waiting for status checks: {'ci/test-api'})"
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_wait_for_checks() -> None:
    """
    test merge.optimistic_updates when we don't have checks to wait for. Since merge.optimistic_updates is disabled we should update the branch.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    config.merge.optimistic_updates = False
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            merging=True,
        )

    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_failing_reviews() -> None:
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review_request = create_review_request()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 2
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[review_request],
        reviews=[
            PRReview(
                state=PRReviewState.CHANGES_REQUESTED,
                createdAt=first_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.COMMENTED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="kodiak", permission=Permission.WRITE),
            ),
        ],
    )
    assert api.set_status.call_count == 1
    assert "changes requested" in api.set_status.calls[0]["msg"]
    assert "chdsbd" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_okay_reviews() -> None:
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review_request = create_review_request()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[review_request],
        reviews=[
            PRReview(
                state=PRReviewState.CHANGES_REQUESTED,
                createdAt=first_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.COMMENTED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
        ],
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_okay_dismissed_reviews() -> None:
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review_request = create_review_request()
    api = create_api()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[review_request],
        reviews=[
            PRReview(
                state=PRReviewState.CHANGES_REQUESTED,
                createdAt=first_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.DISMISSED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.WRITE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
        ],
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_okay_non_member_reviews() -> None:
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()
    review_request = create_review_request()
    api = create_api()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)

    await mergeable(
        api=api,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[review_request],
        reviews=[
            PRReview(
                state=PRReviewState.CHANGES_REQUESTED,
                createdAt=first_review_date,
                author=PRReviewAuthor(login="chdsbd", permission=Permission.NONE),
            ),
            PRReview(
                state=PRReviewState.APPROVED,
                createdAt=latest_review_date,
                author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
            ),
        ],
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge_with_update_branch_immediately_waiting_for_checks() -> None:
    """
    merge.do_not_merge is only useful with merge.update_branch_immediately, 
    Test when PR doesn't need update but is waiting for checks to finish.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    config = create_config()
    branch_protection = create_branch_protection()
    context = create_context()
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    config.merge.do_not_merge = True
    config.merge.update_branch_immediately = True
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    context.context = "ci/test-api"
    context.state = StatusState.PENDING

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        contexts=[context],
    )
    assert api.set_status.called is True
    assert (
        "waiting for required status checks: {'ci/test-api'}"
        in api.set_status.calls[0]["msg"]
    )

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_update_username_blacklist() -> None:
    """
    Kodiak should not update PR if user is blacklisted.
    """
    mergeable = create_mergeable()

    blacklist_config = create_config()
    blacklist_config.update.always = True
    blacklist_config.update.blacklist_usernames = ["mr-test"]
    blacklist_config.update.require_automerge_label = True

    ignored_config = create_config()
    ignored_config.update.always = True
    ignored_config.update.ignored_usernames = ["mr-test"]
    ignored_config.update.require_automerge_label = True

    pull_request = create_pull_request()
    pull_request.author.login = "mr-test"
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND

    branch_protection = create_branch_protection()
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]

    check_run = create_check_run()
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

    for is_merging in (True, False):
        for config in (blacklist_config, ignored_config):
            api = create_api()
            await mergeable(
                api=api,
                config=config,
                pull_request=pull_request,
                branch_protection=branch_protection,
                check_runs=[check_run],
                merging=is_merging,
            )
            assert api.update_branch.call_count == 0
            assert api.set_status.call_count == 1
            assert "updates blocked by update." in api.set_status.calls[0]["msg"]
            assert api.dequeue.call_count == 1

            assert api.queue_for_merge.call_count == 0
            assert api.merge.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_always_enabled_merging_behind_pull_request() -> None:
    """
    When we're merging with update.always enabled we don't want to update the
    branch using our update.always logic. We want to update using our merging
    logic so we trigger the PollForever exception necessary to continue our
    merge loop. If we used the update.always logic we'd eject a PR if it became
    out of sync during merge.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()

    config.update.always = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert api.update_branch.call_count == 1
    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_requires_conversation_resolution() -> None:
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    pull_request.reviewThreads.nodes = [
        ReviewThread(isCollapsed=True),
        ReviewThread(isCollapsed=False),
    ]
    branch_protection.requiresConversationResolution = True

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
    )
    assert api.set_status.call_count == 1
    assert "cannot merge (unresolved review threads)" in api.set_status.calls[0]["msg"]


@pytest.mark.asyncio
async def test_mergeable_uncollapsed_reviews() -> None:
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    branch_protection = create_branch_protection()

    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    pull_request.reviewThreads.nodes = [
        ReviewThread(isCollapsed=True),
        ReviewThread(isCollapsed=False),
    ]

    await mergeable(
        api=api,
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
    )
    assert api.set_status.call_count == 1
    assert (
        "cannot merge (Merging blocked by GitHub requirements)"
        in api.set_status.calls[0]["msg"]
    )
