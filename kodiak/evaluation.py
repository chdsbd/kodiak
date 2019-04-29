import typing
from enum import Enum, auto
from dataclasses import dataclass

from kodiak import config
from kodiak.queries import PullRequest, PullRequestState, MergeStateStatus, RepoInfo


class MergeErrors(str, Enum):
    MISSING_WHITELIST_LABEL = auto()
    MISSING_BLACKLIST_LABEL = auto()
    PR_MERGED = auto()
    PR_CLOSED = auto()


@dataclass
class Failure:
    problems: typing.List[MergeErrors]


class Success:
    pass


async def valid_merge_methods(cfg: config.V1, repo: RepoInfo) -> bool:
    if cfg.merge.method == config.MergeMethod.merge:
        return repo.merge_commit_allowed
    if cfg.merge.method == config.MergeMethod.squash:
        return repo.squash_merge_allowed
    if cfg.merge.method == config.MergeMethod.rebase:
        return repo.rebase_merge_allowed
    raise TypeError("Unknown value")


# TOOD: Accumulate all errors instead of returning at first error. We can
# probably extend that to display a status check on the PR (is there a risk for
# a loop there?)
async def evaluate_mergability(
    config: config.V1, pull_request: PullRequest
) -> typing.Union[Success, Failure]:
    """
    Process a PR to potentially be merged

    A PR is able to be merged if:

    1. Labeled with `AUTOMERGE_LABEL`
    2. Rrequired statuses and check runs are successful
    3. PR has required approvals
    4. PR is up-to-date with target. If this last case fails, we will place the
       PR on the queue for serial integration into target.
    """
    problems: typing.List[MergeErrors] = []

    # TODO: Evaluate merge method viability

    # If we don't have a whitelist, we continue.
    if config.merge.whitelist:
        has_label = any(
            True
            for label in config.merge.whitelist
            if label in set(pull_request.labels)
        )
        # if we don't have a label, ensure the PR is not enqueued and return
        if not has_label:
            # TODO: Dequeue
            problems.append(MergeErrors.MISSING_WHITELIST_LABEL)
    # If we have any blacklist label, we should stop
    if config.merge.blacklist:
        has_label = any(
            True
            for label in config.merge.whitelist
            if label in set(pull_request.labels)
        )
        if has_label:
            # TODO: Dequeue
            problems.append(MergeErrors.MISSING_BLACKLIST_LABEL)

    if pull_request.state == PullRequestState.MERGED:
        problems.append(MergeErrors.PR_MERGED)
    if pull_request.state == PullRequestState.CLOSED:
        problems.append(MergeErrors.PR_CLOSED)

    if (
        pull_request.mergeStateStatus == MergeStateStatus.UNKNOWN
        and pull_request.state != PullRequestState.MERGED
    ):
        # TODO: Retry until we can get a usable status
        raise NotImplementedError()
    if pull_request.mergeStateStatus == MergeStateStatus.BEHIND:
        # TODO: Enqueue pull request for update
        raise NotImplementedError()
    if pull_request.mergeStateStatus in (
        MergeStateStatus.DIRTY,
        MergeStateStatus.DRAFT,
        MergeStateStatus.UNSTABLE,
        MergeStateStatus.BLOCKED,
    ):
        raise NotImplementedError()

    if problems:
        return Failure(problems=problems)
    assert pull_request.mergeStateStatus in (
        MergeStateStatus.CLEAN,
        MergeStateStatus.HAS_HOOKS,
    )
    return Success()
