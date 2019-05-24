from datetime import datetime, timedelta

import pytest

from kodiak.config import V1, MergeMethod
from kodiak.evaluation import (
    MissingGithubMergabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
    mergable,
)
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    CommentAuthorAssociation,
    MergableState,
    MergeStateStatus,
    PRReview,
    PRReviewAuthor,
    PRReviewState,
    PullRequest,
    PullRequestState,
    StatusContext,
    StatusState,
)


@pytest.fixture
def pull_request() -> PullRequest:
    return PullRequest(
        id="254",
        mergeStateStatus=MergeStateStatus.CLEAN,
        state=PullRequestState.OPEN,
        mergeable=MergableState.MERGEABLE,
        labels=["bugfix", "automerge"],
        latest_sha="f89be6c",
        baseRefName="master",
        headRefName="feature/hello-world",
        title="new feature",
        bodyText="some description",
    )


@pytest.fixture
def config() -> V1:
    cfg = V1(version=1)
    cfg.merge.whitelist = ["automerge"]
    cfg.merge.blacklist = []
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


def test_failing_whitelist(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.labels = []
    config.merge.whitelist = ["automerge"]
    config.merge.blacklist = []
    with pytest.raises(NotQueueable, match="whitelist"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )


def test_empty_whitelist(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.labels = ["bug"]
    config.merge.whitelist = []
    with pytest.raises(NotQueueable, match="missing whitelist"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )


def test_blacklisted(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    # a PR with a blacklisted label should not be mergeable
    with pytest.raises(NotQueueable, match="blacklist"):
        pull_request.labels = ["automerge", "dont-merge"]
        config.merge.whitelist = ["automerge"]
        config.merge.blacklist = ["dont-merge"]
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge, MergeMethod.squash],
        )


def test_bad_merge_method_config(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(NotQueueable, match="merge method"):
        config.merge.method = MergeMethod.squash
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.merge],
        )


def test_merged(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    with pytest.raises(NotQueueable, match="merged"):
        pull_request.state = PullRequestState.MERGED
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
    with pytest.raises(NotQueueable, match="merge conflict"):
        pull_request.mergeStateStatus = MergeStateStatus.DIRTY
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
    with pytest.raises(MissingGithubMergabilityState):
        pull_request.mergeable = MergableState.UNKNOWN
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
    with pytest.raises(NotQueueable, match="blocking review"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_missing_review_count(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
) -> None:
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiredApprovingReviewCount = 2
    with pytest.raises(NotQueueable, match="missing required review count"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


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
    with pytest.raises(NotQueueable, match="failing required status checks"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


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
    mergable(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests_count=0,
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
    with pytest.raises(WaitingForChecks, match="missing required status checks"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


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
    with pytest.raises(NotQueueable, match="failing required status checks"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


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
    with pytest.raises(WaitingForChecks, match="missing required status checks"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


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
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
    with pytest.raises(NotQueueable, match="determine why PR is blocked"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=0,
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
) -> None:
    config.block_on_reviews_requested = True
    with pytest.raises(NotQueueable, match="reviews requested"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
            reviews=[review],
            contexts=[context],
            check_runs=[],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_regression_error_before_update(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    check_run: CheckRun,
) -> None:
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/backend", "wip-app"]
    branch_protection.requiresStrictStatusChecks = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    contexts = [StatusContext(context="ci/backend", state=StatusState.SUCCESS)]
    check_run.name = "wip-app"
    check_run.conclusion = CheckConclusionState.SUCCESS
    with pytest.raises(NeedsBranchUpdate):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
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
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.COMMENTED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="ghost"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="kodiak"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
    ]
    with pytest.raises(NotQueueable, match="blocking review"):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
            reviews=reviews,
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
        )


def test_regression_mishandling_multiple_reviews_okay_reviews(
    pull_request: PullRequest,
    config: V1,
    branch_protection: BranchProtectionRule,
    check_run: CheckRun,
    context: StatusContext,
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
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.COMMENTED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="ghost"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
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
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.DISMISSED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="ghost"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
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
            author=PRReviewAuthor(login="chdsbd"),
            authorAssociation=CommentAuthorAssociation.NONE,
        ),
        PRReview(
            state=PRReviewState.APPROVED,
            createdAt=latest_review_date,
            author=PRReviewAuthor(login="ghost"),
            authorAssociation=CommentAuthorAssociation.CONTRIBUTOR,
        ),
    ]
    with pytest.raises(NeedsBranchUpdate):
        mergable(
            config=config,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests_count=1,
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
    mergable(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests_count=0,
        reviews=[review],
        contexts=[context],
        check_runs=[],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
    )
