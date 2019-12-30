from datetime import datetime
from typing import Any, List, Mapping, Optional

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
    PRReviewState,
    PullRequest,
    PullRequestState,
    StatusContext,
    StatusState,
)


class BaseMockFunc:
    func: str

    def __init__(self, calls: Mapping[str, List[Mapping[str, Any]]]) -> None:
        self._total_calls = calls

    def log_call(self, args: dict) -> None:
        self._total_calls[self.func].append(args)

    @property
    def calls(self) -> List[Mapping[str, Any]]:
        return self._total_calls[self.func]

    @property
    def call_count(self) -> int:
        return len(self.calls)


class MockDequeue(BaseMockFunc):
    func = "dequeue"

    async def __call__(self) -> None:
        self.log_call(dict())


class MockSetStatus(BaseMockFunc):
    func = "set_status"

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
    func = "delete_branch"

    async def __call__(self, branch_name: str) -> None:
        self.log_call(dict(branch_name=branch_name))


class MockRemoveLabel(BaseMockFunc):
    func = "remove_label"

    async def __call__(self, label: str) -> None:
        self.log_call(dict(label=label))


class MockCreateComment(BaseMockFunc):
    func = "create_comment"

    async def __call__(self, body: str) -> None:
        self.log_call(dict(body=body))


class MockTriggerTestCommit(BaseMockFunc):
    func = "trigger_test_commit"

    async def __call__(self) -> None:
        self.log_call(dict())


class MockMerge(BaseMockFunc):
    func = "merge"

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
    func = "queue_for_merge"

    async def __call__(self,) -> None:
        self.log_call(dict())


class MockUpdateBranch(BaseMockFunc):
    func = "update_branch"

    async def __call__(self,) -> None:
        self.log_call(dict())


class MockPrApi:
    calls: Mapping[str, List[Mapping[str, Any]]] = dict()

    def not_called(self) -> bool:
        return len(self.calls.keys()) == 0

    dequeue = MockDequeue(calls)
    set_status = MockSetStatus(calls)
    delete_branch = MockDeleteBranch(calls)
    remove_label = MockRemoveLabel(calls)
    create_comment = MockCreateComment(calls)
    trigger_test_commit = MockTriggerTestCommit(calls)
    merge = MockMerge(calls)
    queue_for_merge = MockQueueForMerge(calls)
    update_branch = MockUpdateBranch(calls)


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


def test_config_fixtures_equal(config_str: str, config: V1) -> None:
    assert config == V1.parse_toml(config_str)


def api_called(api: PRAPI) -> bool:
    methods = (
        "dequeue",
        "set_status",
        "delete_branch",
        "remove_label",
        "create_comment",
        "trigger_test_commit",
        "merge",
        "queue_for_merge",
        "update_branch",
    )
    for method in methods:
        if getattr(api, method).call_count > 0:
            return True
    return False


def api_not_called(api: PRAPI) -> bool:
    return not api_called(api)


@pytest.mark.asyncio
async def test_mergeable_abort_is_active_merge(
    api: PRAPI,
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
    assert api_not_called(api)


@pytest.mark.asyncio
async def test_mergeable_error_on_invalid_args(
    api: PRAPI,
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
    We shouldn't be able to set merging=True and is_active_merge=True because merging indicates that this function is being called from the merge queue but is_active_merge indicates that the function is being called from the frontend.
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
    assert api_not_called(api)
    assert "merging" in str(e)


@pytest.mark.asyncio
async def test_mergeable_config_error_sets_warning(
    api: MockPrApi,
    config: V1,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
) -> None:
    """
    If we have a problem finding or parsing a configuration error we should set a status and remove our item from the merge queue.
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
