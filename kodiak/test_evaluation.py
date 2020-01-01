import inspect
from datetime import datetime
from typing import Any, List, Mapping, Optional, Tuple

import pytest
from toml import TomlDecodeError

from kodiak.config import V1, MergeMethod
from kodiak.evaluation import PRAPI, mergeable
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


class BaseMockFunc:
    calls: List[Mapping[str, Any]]

    def __init__(self) -> None:
        self.calls = []

    def log_call(self, args: dict) -> None:
        self.calls.append(args)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def called(self) -> bool:
        return self.call_count > 0


class MockDequeue(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockSetStatus(BaseMockFunc):
    async def __call__(
        self,
        msg: str,
        *,
        latest_commit_sha: str,
        markdown_content: Optional[str] = None,
    ) -> None:
        self.log_call(
            dict(
                msg=msg,
                latest_commit_sha=latest_commit_sha,
                markdown_content=markdown_content,
            )
        )


class MockDeleteBranch(BaseMockFunc):
    async def __call__(self, branch_name: str) -> None:
        self.log_call(dict(branch_name=branch_name))


class MockRemoveLabel(BaseMockFunc):
    async def __call__(self, label: str) -> None:
        self.log_call(dict(label=label))


class MockCreateComment(BaseMockFunc):
    async def __call__(self, body: str) -> None:
        self.log_call(dict(body=body))


class MockTriggerTestCommit(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockMerge(BaseMockFunc):
    async def __call__(
        self,
        merge_method: str,
        commit_title: Optional[str],
        commit_message: Optional[str],
    ) -> None:
        self.log_call(
            dict(
                merge_method=merge_method,
                commit_title=commit_title,
                commit_message=commit_message,
            )
        )


class MockQueueForMerge(BaseMockFunc):
    return_value: Optional[int] = None

    async def __call__(self) -> Optional[int]:
        self.log_call(dict())
        return self.return_value


class MockUpdateBranch(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockPrApi:
    def __init__(self) -> None:
        self.dequeue = MockDequeue()
        self.set_status = MockSetStatus()
        self.delete_branch = MockDeleteBranch()
        self.remove_label = MockRemoveLabel()
        self.create_comment = MockCreateComment()
        self.trigger_test_commit = MockTriggerTestCommit()
        self.merge = MockMerge()
        self.queue_for_merge = MockQueueForMerge()
        self.update_branch = MockUpdateBranch()

    @property
    def api_methods(self) -> List[Tuple[str, BaseMockFunc]]:
        return inspect.getmembers(self, lambda x: isinstance(x, BaseMockFunc))

    @property
    def calls(self) -> Mapping[str, List[Mapping[str, Any]]]:
        return {name: obj.calls for name, obj in self.api_methods}

    def not_called(self) -> bool:
        return len(self.calls.keys()) == 0


@pytest.fixture
def api() -> PRAPI:
    return MockPrApi()


@pytest.fixture
def config_str() -> str:
    return """\
version = 1

[merge]
automerge_label = "automerge"
blacklist_labels = []
method = "squash"
"""


@pytest.fixture
def config() -> V1:
    cfg = V1(version=1)
    cfg.merge.automerge_label = "automerge"
    cfg.merge.blacklist_labels = []
    cfg.merge.method = MergeMethod.squash
    return cfg


@pytest.fixture
def config_path() -> str:
    return "master:.kodiak.toml"


@pytest.fixture
def pull_request() -> PullRequest:
    return PullRequest(
        id="FDExOlB1bGxSZXX1ZXN0MjgxODQ0Nzg7",
        number=142,
        mergeStateStatus=MergeStateStatus.CLEAN,
        state=PullRequestState.OPEN,
        mergeable=MergeableState.MERGEABLE,
        isCrossRepository=False,
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
def review() -> PRReview:
    return PRReview(
        state=PRReviewState.APPROVED,
        createdAt=datetime(2015, 5, 25),
        author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
    )


@pytest.fixture
def context() -> StatusContext:
    return StatusContext(context="ci/api", state=StatusState.SUCCESS)


@pytest.fixture
def check_run() -> CheckRun:
    return CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)


@pytest.fixture
def review_request() -> PRReviewRequest:
    return PRReviewRequest(name="ghost")


def test_config_fixtures_equal(config_str: str, config: V1) -> None:
    assert config == V1.parse_toml(config_str)


@pytest.mark.asyncio
async def test_mergeable_passing(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    This is the happy case where we want to enqueue the PR for merge.
    """
    api.queue_for_merge.return_value = 3
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_abort_is_active_merge(
    api: MockPrApi,
    config: V1,
    config_str: str,
    config_path: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    If we set is_active_merge, that means that in the merge queue the current PR
    is being updated/merged, so in the frontend we don't want to act on the PR
    because the PR is being handled.
    """
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        #
        is_active_merge=True,
    )
    assert api.not_called

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_error_on_invalid_args(
    api: MockPrApi,
    config: V1,
    config_str: str,
    config_path: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    We shouldn't be able to set merging=True and is_active_merge=True because
    merging indicates that this function is being called from the merge queue
    but is_active_merge indicates that the function is being called from the
    frontend.
    """
    with pytest.raises(AssertionError) as e:
        await mergeable(
            api=api,
            config=config,
            config_str=config_str,
            config_path=config_path,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
            #
            merging=True,
            is_active_merge=True,
        )
    assert api.not_called
    assert "merging" in str(e)

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_config_error_sets_warning(
    api: MockPrApi,
    config_path: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    If we have a problem finding or parsing a configuration error we should set
    a status and remove our item from the merge queue.
    """
    broken_config_str = "something[invalid["
    broken_config = V1.parse_toml(broken_config_str)
    assert isinstance(broken_config, TomlDecodeError)

    await mergeable(
        api=api,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        #
        config=broken_config,
        config_str=broken_config_str,
    )
    assert api.set_status.call_count == 1
    assert "Invalid configuration" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_different_app_id(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    If our app id doesn't match the one in the config, we shouldn't touch the repo.
    """
    config.app_id = "1234567"
    our_fake_app_id = "909090"
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        #
        app_id=our_fake_app_id,
    )
    assert api.not_called

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_missing_branch_protection(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    We should warn when we cannot retrieve branch protection settings.
    """
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        #
        branch_protection=None,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "config error" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_requires_commit_signatures(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    requiresCommitSignatures doesn't work with Kodiak.
    """
    branch_protection.requiresCommitSignatures = True
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert (
        '"Require signed commits" branch protection is not supported'
        in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_missing_automerge_label(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    requiresCommitSignatures doesn't work with Kodiak.
    """
    assert config.merge.require_automerge_label
    pull_request.labels = []
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_has_blacklist_labels(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    requiresCommitSignatures doesn't work with Kodiak.
    """
    config.merge.blacklist_labels = ["dont merge!"]
    pull_request.labels = ["bug", "dont merge!", "needs review"]

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_blacklist_title_regex(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    block merge if title regex matches pull request
    """
    pull_request.title = "WIP: add new feature"
    config.merge.blacklist_title_regex = "^WIP.*"

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "matches blacklist_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_draft_pull_request(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    block merge if pull request is in draft state
    """
    pull_request.mergeStateStatus = MergeStateStatus.DRAFT

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "in draft state" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_invalid_merge_method(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    block merge if configured merge method is not enabled
    """
    config.merge.method = MergeMethod.squash

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        merging=False,
        is_active_merge=False,
        #
        valid_merge_methods=[MergeMethod.merge],
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "config error" in api.set_status.calls[0]["msg"]
    assert (
        "configured merge.method 'squash' is invalid" in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_block_on_reviews_requested(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
    review_request: PRReviewRequest,
) -> None:
    """
    block merge if reviews are requested and merge.block_on_reviews_requested is
    enabled.
    """
    config.merge.block_on_reviews_requested = True

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[review_request],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "reviews requested: ['ghost']" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_no_delete_branch(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config disabled.
    """
    pull_request.state = PullRequestState.MERGED
    config.merge.delete_branch_on_merge = False

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config enabled.
    """
    pull_request.state = PullRequestState.MERGED
    config.merge.delete_branch_on_merge = True

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 1
    assert api.delete_branch.calls[0]["branch_name"] == pull_request.headRefName

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch_cross_repo_pr(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config enabled, but we use a
    cross repository (fork) pull request, which we aren't able to delete. We
    shouldn't try to delete the branch.
    """
    pull_request.state = PullRequestState.MERGED
    pull_request.isCrossRepository = True
    config.merge.delete_branch_on_merge = True

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_closed(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR is closed we don't want to act on it.
    """
    pull_request.state = PullRequestState.CLOSED

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label.
    """
    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = False

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 0
    assert api.create_comment.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label.
    """
    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = True

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 1
    assert api.create_comment.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_no_require_automerge_label(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label.
    """
    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = False

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 0
    assert api.create_comment.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_pull_request_need_test_commit(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    When you view a PR on GitHub, GitHub makes a test commit to see if a PR can
    be merged cleanly, but calling through the api doesn't trigger this test
    commit unless we explictly call the GET endpoint for a pull request.
    """
    pull_request.mergeable = MergeableState.UNKNOWN

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.trigger_test_commit.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called


@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't
    have enought approving reviews.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called

@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_has_review_with_missing_perms(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't have enough reviews. If a reviewer doesn't have permissions we should ignore their review.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.READ

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called

@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_changes_requested(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    Don't merge when branch protection requires approving reviews and a user requested changes.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    review.state = PRReviewState.CHANGES_REQUESTED
    review.author.permission = Permission.WRITE

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "changes requested by 'ghost'" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called

@pytest.mark.asyncio
async def test_mergeable_missing_required_approving_reviews_missing_approving_review_count(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    Don't merge when branch protection requires approving reviews and we don't have enough.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 2
    review.state = PRReviewState.APPROVED
    review.author.permission = Permission.WRITE

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
    )
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "missing required reviews, have 1/2" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert not api.update_branch.called
    assert not api.merge.called
    assert not api.queue_for_merge.called
