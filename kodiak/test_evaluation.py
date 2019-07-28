from datetime import datetime, timedelta
from typing import List

import pytest

from kodiak.config import V1, MergeMethod
from kodiak.errors import (
    BranchMerged,
    MergeBlocked,
    MergeConflict,
    MissingAppID,
    MissingGithubMergeabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
)
from kodiak.evaluation import mergeable
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    MergeableState,
    MergeStateStatus,
    Permission,
    PRReview,
    PRReviewAuthor,
    PRReviewRequest,
    PRReviewState,
    PullRequest,
    PullRequestState,
    StatusContext,
    StatusState,
)


@pytest.fixture
def pull_request() -> PullRequest:
    return PullRequest(
        id="FDExOlB1bGxSZXX1ZXN0MjgxODQ0Nzg7",
        number=142,
        mergeStateStatus=MergeStateStatus.CLEAN,
        state=PullRequestState.OPEN,
        mergeable=MergeableState.MERGEABLE,
        isCrossRepository=True,
        labels=["bugfix", "automerge"],
        latest_sha="f89be6c",
        baseRefName="master",
        headRefName="feature/hello-world",
        title="new feature",
        body="# some description",
        bodyText="some description",
        bodyHTML="<h1>some description</h1>",
    )


@pytest.fixture
def config() -> V1:
    cfg = V1(version=1)
    cfg.merge.automerge_label = "automerge"
    cfg.merge.blacklist_labels = []
    cfg.merge.method = MergeMethod.squash
    return cfg


@pytest.fixture
def branch_protection() -> BranchProtectionRule:
    return BranchProtectionRule(
        requiresApprovingReviews=True,
        requiredApprovingReviewCount=1,
        requiresStatusChecks=True,
        requiredStatusCheckContexts=["ci/api"],
        requiresStrictStatusChecks=True,
        requiresCommitSignatures=False,
    )


@pytest.fixture
def check_run() -> CheckRun:
    return CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)


def test_missing_automerge_label(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    review_request: PRReviewRequest,
    context: StatusContext,
) -> None:
    pull_request.labels = ["bug"]
    config.merge.automerge_label = "lgtm"
    with pytest.raises(NotQueueable, match="missing automerge_label") as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )
    assert config.merge.automerge_label in str(e.value)


def test_require_automerge_label_false(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    """
    If the automerge_label is missing, but we have require_automerge_label set
    to false, enqueue the PR for merge
    """
    pull_request.labels = []
    config.merge.automerge_label = "automerge"
    config.merge.require_automerge_label = False
    mergeable(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
    )


def test_blacklist_labels(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    # a PR with a blacklisted label should not be mergeable
    with pytest.raises(NotQueueable, match="blacklist") as e:
        pull_request.labels = ["automerge", "dont-merge"]
        config.merge.automerge_label = "automerge"
        config.merge.blacklist_labels = ["dont-merge"]
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )
    assert "dont-merge" in str(e.value)


def test_blacklist_title_match(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    # a PR with a blacklisted title should not be mergeable
    with pytest.raises(NotQueueable, match="blacklist_title") as e_info:
        config.merge.blacklist_title_regex = "^WIP:.*"
        pull_request.title = "WIP: add fleeb to plumbus"
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )
    assert config.merge.blacklist_title_regex in str(e_info.value)


def test_bad_merge_method_config(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(NotQueueable, match="merge.method") as e:
        config.merge.method = MergeMethod.squash
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge],
        )
    assert config.merge.method.value in str(e.value)
    assert MergeMethod.merge.value in str(e.value)
    assert "<MergeMethod" not in str(
        e.value
    ), "we don't want the repr value, we want the simple str value"


def test_merged(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(BranchMerged):
        pull_request.state = PullRequestState.MERGED
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_closed(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(NotQueueable, match="closed"):
        pull_request.state = PullRequestState.CLOSED
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_merge_conflict(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(MergeConflict):
        pull_request.mergeStateStatus = MergeStateStatus.DIRTY
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_need_update(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(NeedsBranchUpdate):
        pull_request.mergeStateStatus = MergeStateStatus.BEHIND
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_missing_mergeability_state(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(MissingGithubMergeabilityState):
        pull_request.mergeable = MergeableState.UNKNOWN
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_blocking_review(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    review.state = PRReviewState.CHANGES_REQUESTED
    with pytest.raises(NotQueueable, match="changes requested") as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert review.author.login in str(e.value)


def test_requires_review_read_user(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    """
    A PR that requires review should not be satisfied by a read only user.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.READ
    branch_protection.requiredApprovingReviewCount = 1
    branch_protection.requiresApprovingReviews = True
    with pytest.raises(NotQueueable, match="missing required reviews") as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert "0/1" in str(e.value)


def test_missing_review_count(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredApprovingReviewCount = 2
    with pytest.raises(NotQueueable, match="missing required reviews") as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )

    assert str(branch_protection.requiredApprovingReviewCount) in str(e.value)
    assert "1" in str(e.value), "we have one review passed via the reviews arg"


def test_failing_contexts(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredStatusCheckContexts = ["ci/backend"]
    context.context = "ci/backend"
    context.state = StatusState.FAILURE
    with pytest.raises(
        NotQueueable, match="failing/incomplete required status checks"
    ) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert "ci/backend" in str(e.value)


def test_passing_checks(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "wip-app"]
    context.context = "ci/backend"
    context.state = StatusState.SUCCESS
    check_run.name = "wip-app"
    check_run.conclusion = CheckConclusionState.SUCCESS
    mergeable(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
    )


def test_incomplete_checks(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "wip-app"]
    context.context = "ci/backend"
    context.state = StatusState.SUCCESS
    check_run.name = "wip-app"
    check_run.conclusion = None
    with pytest.raises(WaitingForChecks) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert e.value.checks == {"wip-app"}


def test_incomplete_checks_with_dont_wait_on_status_checks(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredStatusCheckContexts = ["wip-app"]
    check_run.name = "wip-app"
    check_run.conclusion = None
    config.merge.dont_wait_on_status_checks = ["wip-app"]
    with pytest.raises(
        NotQueueable, match="failing/incomplete required status checks"
    ) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert "wip-app" in str(e.value)


def test_failing_checks(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "wip-app"]
    context.context = "ci/backend"
    context.state = StatusState.SUCCESS
    check_run.name = "wip-app"
    check_run.conclusion = CheckConclusionState.FAILURE
    with pytest.raises(
        NotQueueable, match="failing/incomplete required status checks"
    ) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert "wip-app" in str(e.value)


def test_missing_required_context(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "ci/frontend"]
    context.context = "ci/backend"
    with pytest.raises(WaitingForChecks) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert e.value.checks == {"ci/frontend"}


@pytest.mark.skip(reason="remove in future PR after hotfix 1/2")
def test_requires_signature(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresCommitSignatures = True
    with pytest.raises(NotQueueable, match="missing required signature"):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_unknown_blockage(
    pull_request: PullRequest, config: V1, branch_protection: BranchProtectionRule
) -> None:
    branch_protection.requiredApprovingReviewCount = 0
    branch_protection.requiresStatusChecks = False
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    with pytest.raises(MergeBlocked):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_dont_update_before_block(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    """
    Regression test for when Kodiak would update a PR that is not mergeable.
    We were raising the NeedsBranchUpdate exception too early.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_block_on_reviews_requested(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    review_request: PRReviewRequest,
) -> None:
    config.merge.block_on_reviews_requested = True
    with pytest.raises(NotQueueable) as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert str(e.value) == "reviews requested: ['ghost']"


def test_regression_error_before_update(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    check_run: CheckRun,
    review_request: PRReviewRequest,
) -> None:
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "wip-app"]
    branch_protection.requiresStrictStatusChecks = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    contexts = [StatusContext(context="ci/backend", state=StatusState.SUCCESS)]
    check_run.name = "wip-app"
    check_run.conclusion = CheckConclusionState.SUCCESS
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=[review],
            check_runs=[check_run],
            contexts=contexts,
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_regression_mishandling_multiple_reviews_failing_reviews(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    check_run: CheckRun,
    context: StatusContext,
    review_request: PRReviewRequest,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 2
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    reviews = [
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
    ]
    with pytest.raises(NotQueueable, match="changes requested") as e:
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=reviews,
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    assert "chdsbd" in str(e.value)


def test_regression_mishandling_multiple_reviews_okay_reviews(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    check_run: CheckRun,
    context: StatusContext,
    review_request: PRReviewRequest,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    reviews = [
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
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=reviews,
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_regression_mishandling_multiple_reviews_okay_dismissed_reviews(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    check_run: CheckRun,
    context: StatusContext,
    review_request: PRReviewRequest,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    reviews = [
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
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=reviews,
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_regression_mishandling_multiple_reviews_okay_non_member_reviews(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    check_run: CheckRun,
    context: StatusContext,
    review_request: PRReviewRequest,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    reviews = [
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
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[review_request],
            reviews=reviews,
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_passing(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    mergeable(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
    )


def test_app_id(
    pull_request: PullRequest, config: V1, branch_protection: BranchProtectionRule
) -> None:
    config.app_id = "123"
    with pytest.raises(MissingAppID):
        mergeable(
            app_id="1234",
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[],
        )
    # try without passing an app_id
    with pytest.raises(MissingAppID):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[],
        )


def test_config_merge_optimistic_updates(
    pull_request: PullRequest, config: V1, branch_protection: BranchProtectionRule
) -> None:
    """
    If optimisitc_updates are enabled, branch updates should be prioritized over
    waiting for running status checks to complete.

    Otherwise, status checks should be checked before updating.
    """
    branch_protection.requiredApprovingReviewCount = 0

    branch_protection.requiresStrictStatusChecks = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND

    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/lint", "ci/test"]
    contexts: List[StatusContext] = []

    config.merge.optimistic_updates = True
    with pytest.raises(NeedsBranchUpdate):
        mergeable(
            app_id="1234",
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=contexts,
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
    config.merge.optimistic_updates = False
    with pytest.raises(WaitingForChecks):
        mergeable(
            app_id="1234",
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=contexts,
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_merge_state_status_draft(
    pull_request: PullRequest, config: V1, branch_protection: BranchProtectionRule
) -> None:
    """
    If optimisitc_updates are enabled, branch updates should be prioritized over
    waiting for running status checks to complete.

    Otherwise, status checks should be checked before updating.
    """
    pull_request.mergeStateStatus = MergeStateStatus.DRAFT

    with pytest.raises(NotQueueable, match="draft state"):
        mergeable(
            app_id="1234",
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_missing_branch_protection(pull_request: PullRequest, config: V1) -> None:
    """
    We don't want to do anything if branch protection is missing
    """

    branch_protection = None
    with pytest.raises(NotQueueable, match="missing branch protection"):
        mergeable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


@pytest.mark.skip(reason="remove in future PR after hotfix 2/2")
def test_requires_commit_signatures(
    pull_request: PullRequest, config: V1, branch_protection: BranchProtectionRule
) -> None:
    """
    If requiresCommitSignatures is enabled in branch protections, kodiak cannot
    function because it cannot create a signed commit to merge the PR.
    """
    branch_protection.requiresCommitSignatures = True
    with pytest.raises(NotQueueable, match='"Require signed commits" not supported.'):
        mergeable(
            app_id="1234",
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[],
            contexts=[],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )
