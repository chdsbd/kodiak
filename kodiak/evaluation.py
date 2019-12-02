import re
from collections import defaultdict
from typing import List, MutableMapping, Optional, Set

import structlog

from kodiak import config
from kodiak.config import MergeMethod
from kodiak.errors import (
    BranchMerged,
    MergeBlocked,
    MergeConflict,
    MissingAppID,
    MissingGithubMergeabilityState,
    MissingSkippableChecks,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
)
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    MergeableState,
    MergeStateStatus,
    Permission,
    PRReview,
    PRReviewRequest,
    PRReviewState,
    PullRequest,
    PullRequestState,
    RepoInfo,
    StatusContext,
    StatusState,
)

logger = structlog.get_logger()


async def valid_merge_methods(cfg: config.V1, repo: RepoInfo) -> bool:
    if cfg.merge.method == config.MergeMethod.merge:
        return repo.merge_commit_allowed
    if cfg.merge.method == config.MergeMethod.squash:
        return repo.squash_merge_allowed
    if cfg.merge.method == config.MergeMethod.rebase:
        return repo.rebase_merge_allowed
    raise TypeError("Unknown value")


def review_status(reviews: List[PRReview]) -> PRReviewState:
    """
    Find the most recent actionable review state for a user
    """
    status = PRReviewState.COMMENTED
    for review in reviews:
        # only these events are meaningful to us
        if review.state in (
            PRReviewState.CHANGES_REQUESTED,
            PRReviewState.APPROVED,
            PRReviewState.DISMISSED,
        ):
            status = review.state
    return status


def mergeable(
    config: config.V1,
    pull_request: PullRequest,
    branch_protection: Optional[BranchProtectionRule],
    review_requests: List[PRReviewRequest],
    reviews: List[PRReview],
    contexts: List[StatusContext],
    check_runs: List[CheckRun],
    valid_signature: bool,
    valid_merge_methods: List[MergeMethod],
    app_id: Optional[str] = None,
) -> None:
    log = logger.bind(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=review_requests,
        reviews=reviews,
        contexts=contexts,
        valid_signature=valid_signature,
        valid_merge_methods=valid_merge_methods,
    )

    # if we have an app_id in the config then we only want to work on this repo
    # if our app_id from the environment matches the configuration.
    if config.app_id is not None and config.app_id != app_id:
        raise MissingAppID("missing required app_id")

    if branch_protection is None:
        raise NotQueueable(
            f"missing branch protection for baseRef: {pull_request.baseRefName!r}"
        )
    if branch_protection.requiresCommitSignatures:
        raise NotQueueable(
            '"Require signed commits" branch protection is not supported. See Kodiak README for more info.'
        )

    if (
        config.merge.require_automerge_label
        and config.merge.automerge_label not in pull_request.labels
    ):
        raise NotQueueable(f"missing automerge_label: {config.merge.automerge_label!r}")
    blacklist_labels = set(config.merge.blacklist_labels) & set(pull_request.labels)
    if blacklist_labels:
        log.info("missing required blacklist labels")
        raise NotQueueable(f"has blacklist_labels: {blacklist_labels!r}")

    if (
        config.merge.blacklist_title_regex
        and re.search(config.merge.blacklist_title_regex, pull_request.title)
        is not None
    ):
        raise NotQueueable(
            f"title matches blacklist_title_regex: {config.merge.blacklist_title_regex!r}"
        )

    if pull_request.mergeStateStatus == MergeStateStatus.DRAFT:
        raise NotQueueable("pull request is in draft state")

    if config.merge.method not in valid_merge_methods:
        valid_merge_methods_str = [method.value for method in valid_merge_methods]
        raise NotQueueable(
            f"configured merge.method {config.merge.method.value!r} is invalid. Valid methods for repo are {valid_merge_methods_str!r}"
        )

    if config.merge.block_on_reviews_requested and review_requests:
        names = [r.name for r in review_requests]
        raise NotQueueable(f"reviews requested: {names!r}")

    if pull_request.state == PullRequestState.MERGED:
        raise BranchMerged()
    if pull_request.state == PullRequestState.CLOSED:
        raise NotQueueable("closed")
    if (
        pull_request.mergeStateStatus == MergeStateStatus.DIRTY
        or pull_request.mergeable == MergeableState.CONFLICTING
    ):
        raise MergeConflict()

    if pull_request.mergeStateStatus == MergeStateStatus.UNSTABLE:
        # TODO: This status means that the pr is mergeable but has failing
        # status checks. we may want to handle this via config
        pass

    if pull_request.mergeable == MergeableState.UNKNOWN:
        # we need to trigger a test commit to fix this. We do that by calling
        # GET on the pull request endpoint.
        raise MissingGithubMergeabilityState("missing mergeablity state")

    if pull_request.mergeStateStatus in (
        MergeStateStatus.BLOCKED,
        MergeStateStatus.BEHIND,
    ):
        # figure out why we can't merge. There isn't a way to get this simply from the Github API. We need to find out ourselves.
        #
        # I think it's possible to find out blockers from branch protection issues
        # https://developer.github.com/v4/object/branchprotectionrule/?#fields
        #
        # - missing reviews
        # - blocking reviews
        # - missing required status checks
        # - failing required status checks
        # - branch not up to date (should be handled before this)
        # - missing required signature
        if (
            branch_protection.requiresApprovingReviews
            and branch_protection.requiredApprovingReviewCount
        ):
            reviews_by_author: MutableMapping[str, List[PRReview]] = defaultdict(list)
            for review in sorted(reviews, key=lambda x: x.createdAt):
                if review.author.permission not in {Permission.ADMIN, Permission.WRITE}:
                    continue
                reviews_by_author[review.author.login].append(review)

            successful_reviews = 0
            for author_name, review_list in reviews_by_author.items():
                review_state = review_status(review_list)
                # blocking review
                if review_state == PRReviewState.CHANGES_REQUESTED:
                    raise NotQueueable(f"changes requested by {author_name!r}")
                # successful review
                if review_state == PRReviewState.APPROVED:
                    successful_reviews += 1
            # missing required review count
            if successful_reviews < branch_protection.requiredApprovingReviewCount:
                raise NotQueueable(
                    f"missing required reviews, have {successful_reviews!r}/{branch_protection.requiredApprovingReviewCount!r}"
                )

        if branch_protection.requiresCommitSignatures and not valid_signature:
            raise NotQueueable("missing required signature")

        required: Set[str] = set()
        passing: Set[str] = set()
        if branch_protection.requiresStatusChecks:
            skippable_contexts: List[str] = []
            failing_contexts: List[str] = []
            pending_contexts: List[str] = []
            passing_contexts: List[str] = []
            required = set(branch_protection.requiredStatusCheckContexts)
            for status_context in contexts:
                # handle dont_wait_on_status_checks. We want to consider a
                # status_check failed if it is incomplete and in the
                # configuration.
                if (
                    status_context.context in config.merge.dont_wait_on_status_checks
                    and status_context.state
                    in (StatusState.EXPECTED, StatusState.PENDING)
                ):
                    skippable_contexts.append(status_context.context)
                    continue
                if status_context.state in (StatusState.ERROR, StatusState.FAILURE):
                    failing_contexts.append(status_context.context)
                elif status_context.state in (
                    StatusState.EXPECTED,
                    StatusState.PENDING,
                ):
                    pending_contexts.append(status_context.context)
                else:
                    assert status_context.state == StatusState.SUCCESS
                    passing_contexts.append(status_context.context)
            for check_run in check_runs:
                if (
                    check_run.name in config.merge.dont_wait_on_status_checks
                    and check_run.conclusion in (None, CheckConclusionState.NEUTRAL)
                ):
                    skippable_contexts.append(check_run.name)
                    continue
                if check_run.conclusion is None:
                    continue
                if check_run.conclusion == CheckConclusionState.SUCCESS:
                    passing_contexts.append(check_run.name)
                if check_run.conclusion in (
                    CheckConclusionState.ACTION_REQUIRED,
                    CheckConclusionState.FAILURE,
                    CheckConclusionState.TIMED_OUT,
                ):
                    failing_contexts.append(check_run.name)
            failing = set(failing_contexts)
            # we have failing statuses that are required
            failing_required_status_checks = failing & required
            # GitHub has undocumented logic for travis-ci checks in GitHub
            # branch protection rules. GitHub compresses
            # "continuous-integration/travis-ci/{pr,pull}" to
            # "continuous-integration/travis-ci". There is only special handling
            # for these specific checks.
            if "continuous-integration/travis-ci" in required:
                if "continuous-integration/travis-ci/pr" in failing:
                    failing_required_status_checks.add(
                        "continuous-integration/travis-ci/pr"
                    )
                if "continuous-integration/travis-ci/pull" in failing:
                    failing_required_status_checks.add(
                        "continuous-integration/travis-ci/pull"
                    )
            if failing_required_status_checks:
                # NOTE(chdsbd): We need to skip this PR because it would block
                # the merge queue. We may be able to bump it to the back of the
                # queue, but it's easier just to remove it all together. There
                # is a similar question for the review counting.

                raise NotQueueable(
                    f"failing required status checks: {failing_required_status_checks!r}"
                )
            if skippable_contexts:
                raise MissingSkippableChecks(skippable_contexts)
            passing = set(passing_contexts)

        need_branch_update = (
            branch_protection.requiresStrictStatusChecks
            and pull_request.mergeStateStatus == MergeStateStatus.BEHIND
        )
        missing_required_status_checks = required - passing
        wait_for_checks = (
            branch_protection.requiresStatusChecks and missing_required_status_checks
        )

        # prioritize branch updates over waiting for status checks to complete
        if config.merge.optimistic_updates:
            if need_branch_update:
                raise NeedsBranchUpdate("behind branch. need update")
            if wait_for_checks:
                raise WaitingForChecks(missing_required_status_checks)
        # almost the same as the pervious case, but we prioritize status checks
        # over branch updates.
        else:
            if wait_for_checks:
                raise WaitingForChecks(missing_required_status_checks)
            if need_branch_update:
                raise NeedsBranchUpdate("behind branch. need update")

        raise MergeBlocked("Merging blocked by GitHub requirements")

    # okay to merge
    return None
