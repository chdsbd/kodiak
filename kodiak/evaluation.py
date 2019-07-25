import re
import typing
from collections import defaultdict
from typing import Optional

import structlog

from kodiak import config
from kodiak.config import MergeMethod
from kodiak.errors import (
    BranchMerged,
    MergeConflict,
    MissingAppID,
    MissingGithubMergeabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
)
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    CommentAuthorAssociation,
    MergeableState,
    MergeStateStatus,
    PRReview,
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


def review_status(reviews: typing.List[PRReview]) -> PRReviewState:
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
    review_requests_count: int,
    reviews: typing.List[PRReview],
    contexts: typing.List[StatusContext],
    check_runs: typing.List[CheckRun],
    valid_signature: bool,
    valid_merge_methods: typing.List[MergeMethod],
    app_id: typing.Optional[str] = None,
) -> None:
    log = logger.bind(
        config=config,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests_count=review_requests_count,
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

    if (
        config.merge.require_automerge_label
        and config.merge.automerge_label not in pull_request.labels
    ):
        raise NotQueueable(
            f"missing automerge_label: {repr(config.merge.automerge_label)}"
        )
    if not set(pull_request.labels).isdisjoint(config.merge.blacklist_labels):
        log.info("missing required blacklist labels")
        raise NotQueueable("has blacklist labels")

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
        # TODO: This is a fatal configuration error. We should provide some notification of this issue
        log.error(
            "invalid configuration. Merge method not possible",
            configured_merge_method=config.merge.method,
            valid_merge_methods=valid_merge_methods,
        )
        raise NotQueueable("invalid merge methods")

    if config.merge.block_on_reviews_requested and review_requests_count:
        raise NotQueueable("reviews requested")

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
            reviews_by_author: typing.MutableMapping[
                str, typing.List[PRReview]
            ] = defaultdict(list)
            for review in sorted(reviews, key=lambda x: x.createdAt):
                # only reviews by members with write access count towards mergeability
                if review.authorAssociation == CommentAuthorAssociation.NONE:
                    continue
                reviews_by_author[review.author.login].append(review)

            successful_reviews = 0
            for review_list in reviews_by_author.values():
                review_state = review_status(review_list)
                # blocking review
                if review_state == PRReviewState.CHANGES_REQUESTED:
                    raise NotQueueable("blocking review")
                # successful review
                if review_state == PRReviewState.APPROVED:
                    successful_reviews += 1
            # missing required review count
            if successful_reviews < branch_protection.requiredApprovingReviewCount:
                raise NotQueueable("missing required review count")

        if branch_protection.requiresCommitSignatures and not valid_signature:
            raise NotQueueable("missing required signature")

        required: typing.Set[str] = set()
        passing: typing.Set[str] = set()
        if branch_protection.requiresStatusChecks:
            failing_contexts: typing.List[str] = []
            pending_contexts: typing.List[str] = []
            passing_contexts: typing.List[str] = []
            required = set(branch_protection.requiredStatusCheckContexts)
            for status_context in contexts:
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
            if len(required - failing) < len(required):
                # NOTE(chdsbd): We need to skip this PR because it would block
                # the merge queue. We may be able to bump it to the back of the
                # queue, but it's easier just to remove it all together. There
                # is a similar question for the review counting.
                raise NotQueueable("failing required status checks")
            passing = set(passing_contexts)

        need_branch_update = (
            branch_protection.requiresStrictStatusChecks
            and pull_request.mergeStateStatus == MergeStateStatus.BEHIND
        )
        wait_for_checks = (
            branch_protection.requiresStatusChecks and len(required - passing) > 0
        )

        # prioritize branch updates over waiting for status checks to complete
        if config.merge.optimistic_updates:
            if need_branch_update:
                raise NeedsBranchUpdate("behind branch. need update")
            if wait_for_checks:
                raise WaitingForChecks("missing required status checks")
        # almost the same as the pervious case, but we prioritize status checks
        # over branch updates.
        else:
            if wait_for_checks:
                raise WaitingForChecks("missing required status checks")
            if need_branch_update:
                raise NeedsBranchUpdate("behind branch. need update")

        raise NotQueueable("Could not determine why PR is blocked")

    # okay to merge
    return None
