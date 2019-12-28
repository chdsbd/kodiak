import re
from collections import defaultdict
from dataclasses import dataclass
from typing import List, MutableMapping, Optional, Set, Union

import pydantic
import structlog
import toml
from typing_extensions import Literal, Protocol

from kodiak import config
from kodiak.config import V1, MergeMethod
from kodiak.errors import PollForever, RetryForSkippableChecks
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


@dataclass
class SetStatus:
    message: str


class Dequeue:
    pass


class Merge:
    pass


class Poll:
    pass


class UpdateBranch:
    pass


class Retry:
    pass


class DeleteBranch:
    pass


class RemoveAutoMergeLabel:
    pass


class AddMergeConflictComment:
    pass


class TriggerTestCommit:
    pass


def fmt_blocked(message: str) -> str:
    return f"🛑 cannot merge ({message})"


def fmt_cfg_err(message: str) -> str:
    return f"⚠️ config error ({message})"


class PRAPI(Protocol):
    def dequeue(self) -> None:
        ...

    def set_status(
        self,
        msg: str,
        *,
        kind: Optional[Literal["cfg_err", "blocked", "loading", "updating"]] = None,
    ) -> None:
        ...

    def delete_branch(self) -> None:
        ...

    def remove_automerge_label(self) -> None:
        ...

    def notify_merge_conflict(self) -> None:
        ...

    def trigger_test_commit(self) -> None:
        ...

    def merge(self) -> None:
        ...

    def update_branch(self) -> None:
        ...


def cfg_err(api: PRAPI, msg: str) -> None:
    api.dequeue()
    api.set_status(msg, kind="cfg_err")


def block_merge(api: PRAPI, msg: str) -> None:
    api.dequeue()
    api.set_status(msg, kind="blocked")


def update_branch(api: PRAPI) -> None:
    api.update_branch()
    api.set_status("updating branch", kind="updating")


def mergeable(
    api: PRAPI,
    config: Union[config.V1, pydantic.ValidationError, toml.TomlDecodeError],
    pull_request: PullRequest,
    branch_protection: Optional[BranchProtectionRule],
    review_requests: List[PRReviewRequest],
    reviews: List[PRReview],
    contexts: List[StatusContext],
    check_runs: List[CheckRun],
    valid_signature: bool,
    valid_merge_methods: List[MergeMethod],
    merging: bool,
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

    if not isinstance(config, V1):
        log.warning("problem fetching config")
        return

    # if we have an app_id in the config then we only want to work on this repo
    # if our app_id from the environment matches the configuration.
    if config.app_id is not None and config.app_id != app_id:
        log.info("missing required app_id")
        api.dequeue()
        return

    if branch_protection is None:
        cfg_err(
            api, f"missing branch protection for baseRef: {pull_request.baseRefName!r}"
        )
        return
    if branch_protection.requiresCommitSignatures:
        cfg_err(
            api,
            '"Require signed commits" branch protection is not supported. See Kodiak README for more info.',
        )
        return

    if (
        config.merge.require_automerge_label
        and config.merge.automerge_label not in pull_request.labels
    ):
        block_merge(api, f"missing automerge_label: {config.merge.automerge_label!r}")
        return
    blacklist_labels = set(config.merge.blacklist_labels) & set(pull_request.labels)
    if blacklist_labels:
        block_merge(api, f"has blacklist_labels: {blacklist_labels!r}")
        return

    if (
        config.merge.blacklist_title_regex
        and re.search(config.merge.blacklist_title_regex, pull_request.title)
        is not None
    ):
        block_merge(
            api,
            f"title matches blacklist_title_regex: {config.merge.blacklist_title_regex!r}",
        )
        return

    if pull_request.mergeStateStatus == MergeStateStatus.DRAFT:
        block_merge(api, "pull request is in draft state")
        return

    if config.merge.method not in valid_merge_methods:
        valid_merge_methods_str = [method.value for method in valid_merge_methods]
        cfg_err(
            api,
            f"configured merge.method {config.merge.method.value!r} is invalid. Valid methods for repo are {valid_merge_methods_str!r}",
        )
        return

    if config.merge.block_on_reviews_requested and review_requests:
        names = [r.name for r in review_requests]
        block_merge(api, f"reviews requested: {names!r}")
        return

    if pull_request.state == PullRequestState.MERGED:
        log.info(
            "pull request merged. config.merge.delete_branch_on_merge=%r",
            config.merge.delete_branch_on_merge,
        )
        api.dequeue()
        if config.merge.delete_branch_on_merge:
            api.delete_branch()
        return

    if pull_request.state == PullRequestState.CLOSED:
        api.dequeue()
        return
    if (
        pull_request.mergeStateStatus == MergeStateStatus.DIRTY
        or pull_request.mergeable == MergeableState.CONFLICTING
    ):
        block_merge(api, "merge conflict")
        # remove label if configured and send message
        if config.merge.notify_on_conflict:
            api.remove_automerge_label()
            api.notify_merge_conflict()
        return

    if pull_request.mergeStateStatus == MergeStateStatus.UNSTABLE:
        # TODO: This status means that the pr is mergeable but has failing
        # status checks. we may want to handle this via config
        pass

    if pull_request.mergeable == MergeableState.UNKNOWN:
        # we need to trigger a test commit to fix this. We do that by calling
        # GET on the pull request endpoint.
        api.trigger_test_commit()
        return

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
                    block_merge(api, f"changes requested by {author_name!r}")
                    return
                # successful review
                if review_state == PRReviewState.APPROVED:
                    successful_reviews += 1
            # missing required review count
            if successful_reviews < branch_protection.requiredApprovingReviewCount:
                block_merge(
                    api,
                    f"missing required reviews, have {successful_reviews!r}/{branch_protection.requiredApprovingReviewCount!r}",
                )
                return

        if branch_protection.requiresCommitSignatures and not valid_signature:
            block_merge(api, "missing required signature")
            return
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
                block_merge(
                    api,
                    f"failing required status checks: {failing_required_status_checks!r}",
                )
                return
            if skippable_contexts:
                # TODO: How do we wait for skippable checks when merging but not when updating?
                if merging:
                    # TODO: retry for a couple times unless we get something useful
                    raise RetryForSkippableChecks
                api.set_status(
                    f"🛑 not waiting for dont_wait_on_status_checks {skippable_contexts!r}"
                )
                return
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
                update_branch(api)
                return
            if wait_for_checks:
                if merging:
                    # TODO: poll
                    api.set_status(
                        "waiting for required status checks: {missing_required_status_checks!r}",
                        kind="loading",
                    )
                    raise PollForever
                return
        # almost the same as the pervious case, but we prioritize status checks
        # over branch updates.
        else:
            if wait_for_checks:
                if merging:
                    # TODO: poll
                    api.set_status(
                        "waiting for required status checks: {missing_required_status_checks!r}",
                        kind="loading",
                    )
                    return
                return
            if need_branch_update:
                update_branch(api)
                return

        block_merge(api, "Merging blocked by GitHub requirements")
        return

    # okay to merge
    api.merge()
    return
