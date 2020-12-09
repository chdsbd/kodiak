import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union

import pydantic
import pytest
from toml import TomlDecodeError
from typing_extensions import Protocol

from kodiak.config import (
    V1,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
)
from kodiak.errors import (
    GitHubApiInternalServerError,
    PollForever,
    RetryForSkippableChecks,
)
from kodiak.evaluation import PRAPI, MergeBody, get_merge_body
from kodiak.evaluation import mergeable as mergeable_func
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    Commit,
    MergeableState,
    MergeStateStatus,
    NodeListPushAllowance,
    Permission,
    PRReview,
    PRReviewAuthor,
    PRReviewRequest,
    PRReviewState,
    PullRequest,
    PullRequestAuthor,
    PullRequestReviewDecision,
    PullRequestState,
    PushAllowance,
    PushAllowanceActor,
    RepoInfo,
    SeatsExceeded,
    StatusContext,
    StatusState,
    Subscription,
    SubscriptionExpired,
    TrialExpired,
)
from kodiak.tests.fixtures import create_commit

log = logging.getLogger(__name__)


class BaseMockFunc:
    calls: List[Mapping[str, Any]]

    def __init__(self) -> None:
        self.calls = []

    def log_call(self, args: Dict[str, Any]) -> None:
        self.calls.append(args)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def called(self) -> bool:
        return self.call_count > 0

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: id={id(self)} call_count={self.call_count!r} called={self.called!r} calls={self.calls!r}>"


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


class MockPullRequestsForRef(BaseMockFunc):
    return_value: Optional[int] = 0

    async def __call__(self, ref: str) -> Optional[int]:
        self.log_call(dict(ref=ref))
        return self.return_value


class MockDeleteBranch(BaseMockFunc):
    async def __call__(self, branch_name: str) -> None:
        self.log_call(dict(branch_name=branch_name))


class MockRemoveLabel(BaseMockFunc):
    async def __call__(self, label: str) -> None:
        self.log_call(dict(label=label))


class MockAddLabel(BaseMockFunc):
    async def __call__(self, label: str) -> None:
        self.log_call(dict(label=label))


class MockCreateComment(BaseMockFunc):
    async def __call__(self, body: str) -> None:
        self.log_call(dict(body=body))


class MockTriggerTestCommit(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockMerge(BaseMockFunc):
    raises: Optional[Union[Type[Exception], Exception]] = None

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
        if self.raises is not None:
            raise self.raises


class MockQueueForMerge(BaseMockFunc):
    # in production we'll frequently have position information.
    # `3` is an arbitrary position.
    return_value: Optional[int] = 3

    async def __call__(self, *, first: bool) -> Optional[int]:
        self.log_call(dict(first=first))
        return self.return_value


class MockUpdateBranch(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockApprovePullRequest(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockRequeue(BaseMockFunc):
    async def __call__(self) -> None:
        self.log_call(dict())


class MockPrApi:
    def __init__(self) -> None:
        self.dequeue = MockDequeue()
        self.requeue = MockRequeue()
        self.set_status = MockSetStatus()
        self.pull_requests_for_ref = MockPullRequestsForRef()
        self.delete_branch = MockDeleteBranch()
        self.remove_label = MockRemoveLabel()
        self.add_label = MockAddLabel()
        self.create_comment = MockCreateComment()
        self.trigger_test_commit = MockTriggerTestCommit()
        self.merge = MockMerge()
        self.queue_for_merge = MockQueueForMerge()
        self.update_branch = MockUpdateBranch()
        self.approve_pull_request = MockApprovePullRequest()

    def get_api_methods(self) -> List[Tuple[str, BaseMockFunc]]:
        cls = type(self)
        members: List[Tuple[str, BaseMockFunc]] = []
        for method_name in dir(self):
            try:
                if isinstance(getattr(cls, method_name), property):
                    continue
            except AttributeError:
                pass
            try:
                if isinstance(getattr(self, method_name), BaseMockFunc):
                    members.append((method_name, getattr(self, method_name)))
            except AttributeError:
                pass

        return members

    @property
    def calls(self) -> Mapping[str, List[Mapping[str, Any]]]:
        return {name: obj.calls for name, obj in self.get_api_methods()}

    @property
    def called(self) -> bool:
        for key, val in self.calls.items():
            if len(val) > 0:
                log.info("MockPrApi.%s called %r time(s)", key, len(val))
                return True
        return False


@pytest.mark.asyncio
async def test_mock_pr_api() -> None:
    api = MockPrApi()
    await api.dequeue()
    assert api.called is True


def create_config_str() -> str:
    return """\
version = 1

[merge]
automerge_label = "automerge"
blacklist_labels = []
method = "squash"
"""


def create_config_path() -> str:
    return "master:.kodiak.toml"


def create_pull_request() -> PullRequest:
    return PullRequest(
        id="FDExOlB1bGxSZXX1ZXN0MjgxODQ0Nzg7",
        number=142,
        author=PullRequestAuthor(
            login="barry", name="Barry Berkman", databaseId=828352, type="User"
        ),
        mergeStateStatus=MergeStateStatus.CLEAN,
        state=PullRequestState.OPEN,
        isDraft=False,
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
        url="https://github.com/example_org/example_repo/pull/65",
    )


def create_branch_protection() -> BranchProtectionRule:
    return BranchProtectionRule(
        requiresApprovingReviews=True,
        requiredApprovingReviewCount=1,
        requiresStatusChecks=True,
        requiredStatusCheckContexts=["ci/api"],
        requiresStrictStatusChecks=True,
        requiresCodeOwnerReviews=True,
        requiresCommitSignatures=False,
        restrictsPushes=False,
        pushAllowances=NodeListPushAllowance(nodes=[]),
    )


def create_review() -> PRReview:
    return PRReview(
        state=PRReviewState.APPROVED,
        createdAt=datetime(2015, 5, 25),
        author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
    )


def create_context() -> StatusContext:
    return StatusContext(context="ci/api", state=StatusState.SUCCESS)


def create_check_run() -> CheckRun:
    return CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)


def create_review_request() -> PRReviewRequest:
    return PRReviewRequest(name="ghost")


def create_repo_info() -> RepoInfo:
    return RepoInfo(
        merge_commit_allowed=True,
        rebase_merge_allowed=True,
        squash_merge_allowed=True,
        delete_branch_on_merge=False,
        is_private=False,
    )


def create_api() -> MockPrApi:
    return MockPrApi()


def create_config() -> V1:
    cfg = V1(version=1)
    cfg.merge.automerge_label = "automerge"
    cfg.merge.blacklist_labels = []
    return cfg


class MergeableType(Protocol):
    """
    A type we define so our create_mergeable() can be typed.
    """

    async def __call__(
        self,
        *,
        api: PRAPI = ...,
        config: Union[V1, pydantic.ValidationError, TomlDecodeError] = ...,
        config_str: str = ...,
        config_path: str = ...,
        pull_request: PullRequest = ...,
        branch_protection: Optional[BranchProtectionRule] = ...,
        review_requests: List[PRReviewRequest] = ...,
        reviews: List[PRReview] = ...,
        contexts: List[StatusContext] = ...,
        check_runs: List[CheckRun] = ...,
        commits: List[Commit] = ...,
        valid_signature: bool = ...,
        valid_merge_methods: List[MergeMethod] = ...,
        merging: bool = ...,
        is_active_merge: bool = ...,
        skippable_check_timeout: int = ...,
        api_call_retry_timeout: int = ...,
        api_call_retry_method_name: Optional[str] = ...,
        repository: RepoInfo = ...,
        subscription: Optional[Subscription] = ...,
        app_id: Optional[str] = ...,
    ) -> None:
        ...


def create_mergeable() -> MergeableType:
    async def mergeable(
        *,
        api: PRAPI = create_api(),
        config: Union[V1, pydantic.ValidationError, TomlDecodeError] = create_config(),
        config_str: str = create_config_str(),
        config_path: str = create_config_path(),
        pull_request: PullRequest = create_pull_request(),
        branch_protection: Optional[BranchProtectionRule] = create_branch_protection(),
        review_requests: List[PRReviewRequest] = [],
        reviews: List[PRReview] = [create_review()],
        contexts: List[StatusContext] = [create_context()],
        check_runs: List[CheckRun] = [create_check_run()],
        commits: List[Commit] = [],
        valid_signature: bool = False,
        valid_merge_methods: List[MergeMethod] = [
            MergeMethod.merge,
            MergeMethod.squash,
            MergeMethod.rebase,
        ],
        merging: bool = False,
        is_active_merge: bool = False,
        skippable_check_timeout: int = 5,
        api_call_retry_timeout: int = 5,
        api_call_retry_method_name: Optional[str] = None,
        repository: RepoInfo = create_repo_info(),
        subscription: Optional[Subscription] = None,
        app_id: Optional[str] = None,
    ) -> None:
        """
            wrapper around evaluation.mergeable that simplifies tests by providing
            default arguments to override.
            """
        return await mergeable_func(
            api=api,
            config=config,
            config_str=config_str,
            config_path=config_path,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=review_requests,
            reviews=reviews,
            contexts=contexts,
            check_runs=check_runs,
            commits=commits,
            valid_signature=valid_signature,
            valid_merge_methods=valid_merge_methods,
            repository=repository,
            merging=merging,
            is_active_merge=is_active_merge,
            skippable_check_timeout=skippable_check_timeout,
            api_call_retry_timeout=api_call_retry_timeout,
            api_call_retry_method_name=api_call_retry_method_name,
            subscription=subscription,
            app_id=app_id,
        )

    return mergeable


@pytest.mark.asyncio
async def test_mergeable_abort_is_active_merge() -> None:
    """
    If we set is_active_merge, that means that in the merge queue the current PR
    is being updated/merged, so in the frontend we don't want to act on the PR
    because the PR is being handled.
    """
    api = create_api()
    mergeable = create_mergeable()
    await mergeable(api=api, is_active_merge=True)
    assert api.queue_for_merge.called is True

    assert (
        api.set_status.call_count == 0
    ), "we don't want to set a status message from the frontend when the PR is being merged"
    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_config_error_sets_warning() -> None:
    """
    If we have a problem finding or parsing a configuration error we should set
    a status and remove our item from the merge queue.
    """
    api = create_api()
    mergeable = create_mergeable()
    broken_config_str = "something[invalid["
    broken_config = V1.parse_toml(broken_config_str)
    assert isinstance(broken_config, TomlDecodeError)

    await mergeable(api=api, config=broken_config, config_str=broken_config_str)
    assert api.set_status.call_count == 1
    assert "Invalid configuration" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_different_app_id() -> None:
    """
    If our app id doesn't match the one in the config, we shouldn't touch the repo.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    config.app_id = "1234567"
    our_fake_app_id = "909090"
    await mergeable(api=api, config=config, app_id=our_fake_app_id)
    assert api.dequeue.called is True

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_branch_protection() -> None:
    """
    We should warn when we cannot retrieve branch protection settings.
    """
    api = create_api()
    mergeable = create_mergeable()

    await mergeable(api=api, branch_protection=None)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "config error" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


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
async def test_mergeable_missing_automerge_label() -> None:
    """
    If we're missing an automerge label we should not merge the PR.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.require_automerge_label = True
    pull_request.labels = []
    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_missing_automerge_label_require_automerge_label() -> None:
    """
    We can work on a PR if we're missing labels and we have require_automerge_label disabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.require_automerge_label = False
    pull_request.labels = []
    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_has_blacklist_labels() -> None:
    """
    blacklist labels should prevent merge
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.blacklist_labels = ["dont merge!"]
    pull_request.labels = ["bug", "dont merge!", "needs review"]

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_has_blocking_labels() -> None:
    """
    blocking labels should prevent merge
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.blocking_labels = ["dont merge!"]
    pull_request.labels = ["bug", "dont merge!", "needs review"]

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_blacklist_title_regex() -> None:
    """
    block merge if blacklist_title_regex matches pull request
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.title = "WIP: add new feature"
    config.merge.blacklist_title_regex = "^WIP.*"

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "matches merge.blacklist_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_blocking_title_regex() -> None:
    """
    block merge if blocking_title_regex matches pull request
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.title = "WIP: add new feature"
    config.merge.blocking_title_regex = "^WIP.*"

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "matches merge.blocking_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_blocking_title_regex_default() -> None:
    """
    We should default to "^WIP.*" if unset.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.title = "WIP: add new feature"
    assert (
        config.merge.blocking_title_regex == ":::|||kodiak|||internal|||reserved|||:::"
    )

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "matches merge.blocking_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_blocking_title_disabled() -> None:
    """
    We should be able to disable the title regex by setting it to empty string.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.title = "WIP: add new feature"
    config.merge.blocking_title_regex = "WIP.*"

    # verify by default we block
    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "matches merge.blocking_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False

    # should disable blocking_title_regex by setting to empty string
    config.merge.blocking_title_regex = ""
    api = create_api()
    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_blacklist_title_match_with_exp_regex(mocker: Any) -> None:
    """
    Ensure Kodiak uses a linear time regex engine.

    When using an exponential engine this test will timeout.
    """
    # a ReDos regex and accompanying string
    # via: https://en.wikipedia.org/wiki/ReDoS#Vulnerable_regexes_in_online_repositories
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    from kodiak.evaluation import re

    kodiak_evaluation_re_search = mocker.spy(re, "search")

    config.merge.blacklist_title_regex = "^(a+)+$"
    pull_request.title = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!"

    await mergeable(api=api, config=config, pull_request=pull_request)
    # we don't really care about the result for this so long as this test
    # doesn't hang the entire suite.
    assert kodiak_evaluation_re_search.called, "we should hit our regex search"


@pytest.mark.asyncio
async def test_mergeable_draft_pull_request() -> None:
    """
    block merge if pull request is in draft state

    `mergeStateStatus.DRAFT` is being removed 2021-01-01.
    https://docs.github.com/en/free-pro-team@latest/graphql/overview/breaking-changes#changes-scheduled-for-2021-01-01
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()

    pull_request.mergeStateStatus = MergeStateStatus.DRAFT

    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "in draft state" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_draft_pull_request_is_draft_field() -> None:
    """
    block merge if pull request is in draft state.

    Test using the `isDraft` field. `mergeStateStatus.DRAFT` is being removed 2021-01-01.
    https://docs.github.com/en/free-pro-team@latest/graphql/overview/breaking-changes#changes-scheduled-for-2021-01-01
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()

    pull_request.isDraft = True

    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "in draft state" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_invalid_merge_method() -> None:
    """
    block merge if configured merge method is not enabled
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    config.merge.method = MergeMethod.squash

    await mergeable(api=api, config=config, valid_merge_methods=[MergeMethod.merge])
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "config error" in api.set_status.calls[0]["msg"]
    assert (
        "configured merge.method 'squash' is invalid" in api.set_status.calls[0]["msg"]
    )

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_default_merge_method() -> None:
    """
    Should default to `merge` commits.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    assert (
        config.merge.method is None
    ), "we shouldn't have specified a value for the merge method. We want to allow the default."

    await mergeable(api=api, config=config, merging=True)
    assert api.merge.call_count == 1
    assert api.merge.calls[0]["merge_method"] == MergeMethod.merge

    assert api.dequeue.called is False
    assert api.queue_for_merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_single_merge_method() -> None:
    """
    If an account only has one merge method configured, use that if they haven't
    specified an option.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    assert config.merge.method is None, "we must not specify a default for this to work"

    await mergeable(
        api=api,
        config=config,
        valid_merge_methods=[
            # Kodiak should select the only valid merge method if `merge.method`
            # is not configured.
            MergeMethod.rebase
        ],
        merging=True,
    )
    assert api.merge.call_count == 1
    assert api.merge.calls[0]["merge_method"] == "rebase"

    assert api.dequeue.called is False
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_two_merge_methods() -> None:
    """
    If we have two options available, choose the first one, based on our ordered
    list of "merge", "squash", "rebase".
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    assert config.merge.method is None, "we must not specify a default for this to work"

    await mergeable(
        api=api,
        config=config,
        valid_merge_methods=[
            # Kodiak should select the first valid merge method if `merge.method`
            # is not configured.
            MergeMethod.squash,
            MergeMethod.rebase,
        ],
        merging=True,
    )
    assert api.merge.call_count == 1
    assert api.merge.calls[0]["merge_method"] == "squash"

    assert api.dequeue.called is False
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_no_valid_methods() -> None:
    """
    We should always have at least one valid_merge_method in production, but
    this is just a test to make sure we handle this case anyway.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    assert config.merge.method is None, "we must not specify a default for this to work"

    await mergeable(api=api, config=config, valid_merge_methods=[])
    assert api.dequeue.call_count == 1
    assert api.set_status.call_count == 1
    assert (
        "configured merge.method 'merge' is invalid." in api.set_status.calls[0]["msg"]
    )

    assert api.merge.called is False
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_method_override_with_label() -> None:
    """
    We should be able to override merge methods with a label.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.method = MergeMethod.squash
    override_labels = (
        # basic
        "kodiak:merge.method='rebase'",
        # spacing
        "kodiak:merge.method= 'rebase'",
        # more spacing
        "kodiak:merge.method = 'rebase'",
        # full spacing
        "kodiak: merge.method = 'rebase'",
        # try with double quotes
        'kodiak:merge.method="rebase"',
    )
    for index, override_label in enumerate(override_labels):
        pull_request.labels = ["automerge", override_label]

        await mergeable(api=api, config=config, pull_request=pull_request, merging=True)
        assert api.merge.call_count == index + 1
        assert api.merge.calls[0]["merge_method"] == MergeMethod.rebase

        assert api.queue_for_merge.called is False
        assert api.dequeue.called is False
        assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_block_on_reviews_requested() -> None:
    """
    block merge if reviews are requested and merge.block_on_reviews_requested is
    enabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    review_request = create_review_request()

    config.merge.block_on_reviews_requested = True

    await mergeable(api=api, config=config, review_requests=[review_request])
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "reviews requested: ['ghost']" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_no_delete_branch() -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config disabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.state = PullRequestState.MERGED
    config.merge.delete_branch_on_merge = False

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch() -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config enabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.state = PullRequestState.MERGED
    config.merge.delete_branch_on_merge = True

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 1
    assert api.delete_branch.calls[0]["branch_name"] == pull_request.headRefName

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch_with_branch_dependencies() -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config enabled, but with other PR dependencies on a branch. If there are open PRs that depend on a branch, we should _not_ delete the branch.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.state = PullRequestState.MERGED
    config.merge.delete_branch_on_merge = True
    api.pull_requests_for_ref.return_value = 1

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch_cross_repo_pr() -> None:
    """
    if a PR is already merged we shouldn't take anymore action on it besides
    deleting the branch if configured.

    Here we test with the delete_branch_on_merge config enabled, but we use a
    cross repository (fork) pull request, which we aren't able to delete. We
    shouldn't try to delete the branch.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    pull_request.state = PullRequestState.MERGED
    pull_request.isCrossRepository = True
    config.merge.delete_branch_on_merge = True

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merged_delete_branch_repo_delete_enabled() -> None:
    """
    If the repository has delete_branch_on_merge enabled we shouldn't bother
    trying to delete the branch.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()
    repository = create_repo_info()

    pull_request.state = PullRequestState.MERGED
    repository.delete_branch_on_merge = True
    config.merge.delete_branch_on_merge = True

    await mergeable(
        api=api, config=config, pull_request=pull_request, repository=repository
    )
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1
    assert api.delete_branch.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_closed() -> None:
    """
    if a PR is closed we don't want to act on it.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()

    pull_request.state = PullRequestState.CLOSED

    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict() -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = False

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 0
    assert api.create_comment.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict() -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = True

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 1
    assert api.create_comment.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_blacklist_title_regex() -> None:
    """
    if a PR has a merge conflict we can't merge. If the title matches the
    blacklist_title_regex we should still leave a comment and remove the
    automerge label.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = True
    config.merge.blacklist_title_regex = "WIP.*"
    pull_request.title = "WIP: add csv download to reports view"

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 1
    assert api.create_comment.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_missing_label() -> None:
    """
    if a PR has a merge conflict we can't merge. If configured, we should leave
    a comment and remove the automerge label. If the automerge label is missing we shouldn't create a comment.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = True
    pull_request.labels = []

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.create_comment.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_automerge_labels() -> None:
    """
    We should only notify on conflict when we have an automerge label.

    If we have an array of merge.automerge_label labels, we should remove each
    one like we do with merge.automerge_label.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = True
    pull_request.labels = ["ship it!!!"]
    config.merge.automerge_label = ["ship it!!!"]

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 1
    assert api.create_comment.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_no_require_automerge_label() -> None:
    """
    if a PR has a merge conflict we can't merge. If require_automerge_label is set then we shouldn't notify even if notify_on_conflict is configured. This allows prevents infinite commenting.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    config.merge.notify_on_conflict = True
    config.merge.require_automerge_label = False

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert "cannot merge" in api.set_status.calls[0]["msg"]
    assert "merge conflict" in api.set_status.calls[0]["msg"]
    assert api.remove_label.call_count == 0
    assert api.create_comment.call_count == 0

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_merge_conflict_notify_on_conflict_pull_request_merged() -> None:
    """
    If the pull request is merged we shouldn't error on merge conflict.


    On merge we will get the following values when we fetch pull request information:

        "mergeStateStatus": "DIRTY"
        "state": "MERGED"
        "mergeable": "CONFLICTING"

    Although the PR is said to be dirty or conflicting, we don't want to leave a
    comment because the pull request is already merged.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    pull_request.mergeStateStatus = MergeStateStatus.DIRTY
    pull_request.mergeable = MergeableState.CONFLICTING
    pull_request.state = PullRequestState.MERGED
    config.merge.notify_on_conflict = True

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.dequeue.call_count == 1

    assert api.set_status.call_count == 0
    assert api.remove_label.call_count == 0
    assert api.create_comment.call_count == 0
    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_need_test_commit() -> None:
    """
    When you view a PR on GitHub, GitHub makes a test commit to see if a PR can
    be merged cleanly, but calling through the api doesn't trigger this test
    commit unless we explictly call the GET endpoint for a pull request.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()

    pull_request.mergeable = MergeableState.UNKNOWN

    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.trigger_test_commit.call_count == 1
    assert api.requeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_need_test_commit_merging() -> None:
    """
    If we're merging a PR we should raise the PollForever exception instead of
    returning. This way we stay in the merge loop.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()

    pull_request.mergeable = MergeableState.UNKNOWN

    with pytest.raises(PollForever):
        await mergeable(api=api, pull_request=pull_request, merging=True)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.trigger_test_commit.call_count == 1
    assert api.requeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_need_test_commit_need_update() -> None:
    """
    If a pull request mergeable status is UNKNOWN we should trigger a test
    commit and queue it for evaluation.

    Regression test, merge.blocking_title_regex should not prevent us for
    triggering a test commit.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    config.update.always = True
    config.merge.blocking_title_regex = "^WIP:.*"
    pull_request.title = "WIP: add(api): endpoint for checking notifications"

    pull_request.mergeable = MergeableState.UNKNOWN
    pull_request.state = PullRequestState.OPEN

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.trigger_test_commit.call_count == 1
    assert api.requeue.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_pull_request_need_test_commit_need_update_pr_not_open() -> None:
    """
    If a pull request mergeable status is UNKNOWN _and_ it is OPEN we should
    trigger a test commit and queue it for evaluation.

    Regression test to prevent infinite loop calling trigger_test_commit on
    merged/closed pull requests.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    config = create_config()

    config.update.always = True
    config.merge.blocking_title_regex = "^WIP:.*"
    pull_request.title = "WIP: add(api): endpoint for checking notifications"

    pull_request.mergeable = MergeableState.UNKNOWN

    # this test is nearly identical to
    # test_mergeable_pull_request_need_test_commit_need_update, except our pull
    # request state is MERGED or CLOSED instead of OPEN.
    for index, pull_request_state in enumerate(
        (PullRequestState.MERGED, PullRequestState.CLOSED)
    ):
        pull_request.state = pull_request_state
        await mergeable(api=api, config=config, pull_request=pull_request)
        assert api.set_status.call_count == index + 1
        assert (
            "cannot merge (title matches merge.blocking_title_regex"
            in api.set_status.calls[0]["msg"]
        )
        assert api.dequeue.call_count == index + 1
        assert api.trigger_test_commit.call_count == 0
        assert api.requeue.call_count == 0

        # verify we haven't tried to update/merge the PR
        assert api.update_branch.called is False
        assert api.merge.called is False
        assert api.queue_for_merge.called is False


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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
async def test_mergeable_unknown_merge_blockage() -> None:
    """
    Test how kodiak behaves when we cannot figure out why a PR is blocked.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED

    await mergeable(api=api, pull_request=pull_request)

    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert api.update_branch.call_count == 0
    assert "Merging blocked by GitHub" in api.set_status.calls[0]["msg"]
    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_prioritize_ready_to_merge() -> None:
    """
    If we enabled merge.prioritize_ready_to_merge, then if a PR is ready to merge when it reaches Kodiak, we merge it immediately. merge.prioritize_ready_to_merge is basically the sibling of merge.update_branch_immediately.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()

    config.merge.prioritize_ready_to_merge = True

    await mergeable(api=api, config=config)

    assert api.set_status.call_count == 2
    assert "attempting to merge PR (merging)" in api.set_status.calls[0]["msg"]
    assert api.set_status.calls[1]["msg"] == "merge complete 🎉"
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 1

    # verify we haven't tried to merge the PR
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_merge() -> None:
    """
    If we're merging we should call api.merge
    """
    mergeable = create_mergeable()
    api = create_api()

    await mergeable(
        api=api,
        #
        merging=True,
    )

    assert api.set_status.call_count == 2
    assert "attempting to merge PR (merging)" in api.set_status.calls[0]["msg"]
    assert api.set_status.calls[1]["msg"] == "merge complete 🎉"
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 1
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_queue_for_merge_no_position() -> None:
    """
    If we're attempting to merge from the frontend we should place the PR on the queue.

    If permission information is unavailable (None) we should not set a status check.
    """
    mergeable = create_mergeable()
    api = create_api()
    api.queue_for_merge.return_value = None
    await mergeable(api=api)

    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 0
    assert api.queue_for_merge.call_count == 1


@pytest.mark.asyncio
async def test_mergeable_passing() -> None:
    """
    This is the happy case where we want to enqueue the PR for merge.
    """
    mergeable = create_mergeable()
    api = create_api()
    await mergeable(api=api)
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_merge_automerge_labels() -> None:
    """
    Test merge.automerge_label array allows a pull request to be merged.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    pull_request.labels = ["ship it!"]
    config = create_config()
    config.merge.automerge_label = ["ship it!"]
    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_need_update() -> None:
    """
    When a PR isn't in the queue but needs an update we should enqueue it for merge.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


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
async def test_mergeable_do_not_merge() -> None:
    """
    merge.do_not_merge should disable merging a PR.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    config.merge.do_not_merge = True
    await mergeable(api=api, config=config)
    assert api.set_status.called is True
    assert "okay to merge" in api.set_status.calls[0]["msg"]

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge_behind_no_update_immediately() -> None:
    """
    merge.do_not_merge without merge.update_branch_immediately means that any PR
    behind target will never get updated. We should display a warning about
    this.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    config.merge.do_not_merge = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND

    await mergeable(api=api, config=config, pull_request=pull_request)
    assert api.set_status.called is True
    assert (
        "need branch update (suggestion: use merge.update_branch_immediately"
        in api.set_status.calls[0]["msg"]
    )
    assert isinstance(api.set_status.calls[0]["markdown_content"], str)

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge_with_update_branch_immediately_no_update() -> None:
    """
    merge.do_not_merge is only useful with merge.update_branch_immediately,
    Test when PR doesn't need update.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()

    config.merge.do_not_merge = True
    config.merge.update_branch_immediately = True
    await mergeable(api=api, config=config)
    assert api.set_status.called is True
    assert "okay to merge" in api.set_status.calls[0]["msg"]

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


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
async def test_mergeable_do_not_merge_with_update_branch_immediately_need_update() -> None:
    """
    merge.do_not_merge is only useful with merge.update_branch_immediately,
    Test when PR needs update.
    """
    mergeable = create_mergeable()
    api = create_api()
    pull_request = create_pull_request()
    config = create_config()
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    config.merge.do_not_merge = True
    config.merge.update_branch_immediately = True
    await mergeable(api=api, config=config, pull_request=pull_request)

    assert api.update_branch.called is True
    assert api.set_status.called is True
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_api_call_retry_timeout() -> None:
    """
    if we enounter too many errors calling GitHub api_call_retry_timeout will be zero. we should notify users via a status check.
    """
    mergeable = create_mergeable()
    api = create_api()
    await mergeable(
        api=api,
        #
        api_call_retry_timeout=0,
        api_call_retry_method_name="update branch",
    )

    assert api.set_status.called is True
    assert (
        "problem contacting GitHub API with method 'update branch'"
        in api.set_status.calls[0]["msg"]
    )
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_api_call_retry_timeout_missing_method() -> None:
    """
    if we enounter too many errors calling GitHub api_call_retry_timeout will be zero. we should notify users via a status check.

    This shouldn't really be possible in reality, but this is a test where the method name is None but the timeout is zero.
    """
    mergeable = create_mergeable()
    api = create_api()

    await mergeable(api=api, api_call_retry_timeout=0, api_call_retry_method_name=None)

    assert api.set_status.called is True
    assert "problem contacting GitHub API" in api.set_status.calls[0]["msg"]
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
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


def test_pr_get_merge_body_full() -> None:
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    title=MergeTitleStyle.pull_request_title,
                    body=MergeBodyStyle.pull_request_body,
                    include_pr_number=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_title=pull_request.title + f" (#{pull_request.number})",
        commit_message=pull_request.body,
    )
    assert expected == actual


def test_pr_get_merge_body_empty() -> None:
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(version=1),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash")
    assert actual == expected


def test_get_merge_body_strip_html_comments() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, strip_html_comments=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello world")
    assert actual == expected

def test_get_merge_body_cut_body_before() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, cut_body_before="<!-- testing -->"
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="world")
    assert actual == expected

def test_get_merge_body_empty() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    actual = get_merge_body(
        config=V1(
            version=1, merge=Merge(message=MergeMessage(body=MergeBodyStyle.empty))
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="")
    assert actual == expected


def test_get_merge_body_includes_pull_request_url() -> None:
    """
    Ensure that when the appropriate config option is set, we include the
    pull request url in the commit message.
    """
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, include_pull_request_url=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65""",
    )
    assert actual == expected


def test_get_merge_body_includes_pull_request_url_with_coauthor() -> None:
    """
    Coauthor should appear after the pull request url
    """
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_url=True,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65

Co-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>""",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_user() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_bot() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Bot"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry[bot] <828352+barry[bot]@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_mannequin() -> None:
    """
    Test case where actor is not a User and Bot to see how we handle weird cases.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Mannequin"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_invalid_body_style() -> None:
    """
    We only include trailers MergeBodyStyle.pull_request_body and
    MergeBodyStyle.empty. Verify we don't include trailers for
    MergeBodyStyle.github_default.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.include_pull_request_author = True

    config.merge.message.body = MergeBodyStyle.github_default
    actual = get_merge_body(
        config=config,
        pull_request=pull_request,
        merge_method=MergeMethod.merge,
        commits=[],
    )
    expected = MergeBody(merge_method="merge", commit_message=None)
    assert actual == expected


def test_get_merge_body_include_coauthors() -> None:
    """
    Verify we include coauthor trailers for MergeBodyStyle.pull_request_body.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.body = MergeBodyStyle.pull_request_body
    config.merge.message.include_coauthors = True
    config.merge.message.include_pull_request_author = False

    actual = get_merge_body(
        config=config,
        merge_method=MergeMethod.merge,
        pull_request=pull_request,
        commits=[
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            create_commit(
                database_id=590434, name="Maeve Millay", login="maeve-m", type="Bot"
            ),
            # we default to the login when name is None.
            create_commit(
                database_id=771233, name=None, login="d-abernathy", type="Bot"
            ),
            # without a databaseID the commit author will be ignored.
            create_commit(database_id=None, name=None, login="william", type="User"),
            # duplicate should be ignored.
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            # merge commits should be ignored. merge commits will have more than
            # one parent.
            create_commit(
                database_id=1,
                name="Arnold Weber",
                login="arnold",
                type="User",
                parents=2,
            ),
            # pull request author should be ignored when
            # include_pull_request_author is not enabled
            create_commit(
                database_id=pull_request.author.databaseId,
                name="Joe PR Author",
                login="j-author",
                type="User",
            ),
        ],
    )
    expected = MergeBody(
        merge_method="merge",
        commit_message="hello world\n\nCo-authored-by: Bernard Lowe <9023904+b-lowe@users.noreply.github.com>\nCo-authored-by: Maeve Millay <590434+maeve-m[bot]@users.noreply.github.com>\nCo-authored-by: d-abernathy[bot] <771233+d-abernathy[bot]@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_coauthors_include_pr_author() -> None:
    """
    We should include the pull request author when configured.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.body = MergeBodyStyle.pull_request_body
    config.merge.message.include_coauthors = True
    config.merge.message.include_pull_request_author = True

    actual = get_merge_body(
        config=config,
        merge_method=MergeMethod.merge,
        pull_request=pull_request,
        commits=[
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            # we should ignore a duplicate entry for the PR author when
            # include_pull_request_author is enabled.
            create_commit(
                database_id=pull_request.author.databaseId,
                name=pull_request.author.name,
                login=pull_request.author.login,
                type=pull_request.author.type,
            ),
        ],
    )
    expected = MergeBody(
        merge_method="merge",
        commit_message=f"hello world\n\nCo-authored-by: {pull_request.author.name} <{pull_request.author.databaseId}+{pull_request.author.login}@users.noreply.github.com>\nCo-authored-by: Bernard Lowe <9023904+b-lowe@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_coauthors_invalid_body_style() -> None:
    """
    We only include trailers for MergeBodyStyle.pull_request_body and MergeBodyStyle.empty. Verify we don't add coauthor trailers for MergeBodyStyle.github_default.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.include_coauthors = True
    config.merge.message.body = MergeBodyStyle.github_default
    actual = get_merge_body(
        config=config,
        pull_request=pull_request,
        merge_method=MergeMethod.merge,
        commits=[
            create_commit(database_id=9023904, name="", login="b-lowe", type="User"),
            create_commit(
                database_id=590434, name="Maeve Millay", login="maeve-m", type="Bot"
            ),
        ],
    )
    expected = MergeBody(merge_method="merge", commit_message=None)
    assert actual == expected


@pytest.mark.asyncio
async def test_mergeable_include_coauthors() -> None:
    """
    Include coauthors should attach coauthor when `merge.message.body = "pull_request_body"`
    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.message.include_coauthors = True

    for body_style, commit_message in (
        (
            MergeBodyStyle.pull_request_body,
            "# some description\n\nCo-authored-by: Barry Block <73213123+b-block@users.noreply.github.com>",
        ),
        (
            MergeBodyStyle.empty,
            "Co-authored-by: Barry Block <73213123+b-block@users.noreply.github.com>",
        ),
    ):
        config.merge.message.body = body_style
        api = create_api()
        await mergeable(
            api=api,
            config=config,
            commits=[
                create_commit(
                    database_id=73213123,
                    name="Barry Block",
                    login="b-block",
                    type="User",
                )
            ],
            merging=True,
        )
        assert api.set_status.call_count == 2
        assert "attempting to merge PR" in api.set_status.calls[0]["msg"]
        assert api.set_status.calls[1]["msg"] == "merge complete 🎉"

        assert api.merge.call_count == 1
        assert commit_message == api.merge.calls[0]["commit_message"]
        assert api.update_branch.call_count == 0
        assert api.queue_for_merge.call_count == 0
        assert api.dequeue.call_count == 0


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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    assert "missing automerge_label:" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_mergeable_passing_update_always_enabled() -> None:
    """
    Test happy case with update.always enabled. We should shouldn't see any
    difference with update.always enabled.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()

    config.update.always = True
    await mergeable(api=api, config=config)
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


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
async def test_mergeable_auto_approve() -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    await mergeable(api=api, config=config, pull_request=pull_request, reviews=[])
    assert api.approve_pull_request.call_count == 1
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_existing_approval() -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    If we have an existing, valid approval, we should not add another.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    review = create_review()
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    review.author.login = "kodiak-test-app"
    review.state = PRReviewState.APPROVED
    await mergeable(api=api, config=config, pull_request=pull_request, reviews=[review])
    assert api.approve_pull_request.call_count == 0
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_old_approval() -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    If we have a dismissed approval, we should add a fresh one.
    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    pull_request = create_pull_request()
    review = create_review()
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    review.author.login = "kodiak-test-app"
    review.state = PRReviewState.DISMISSED
    await mergeable(api=api, config=config, pull_request=pull_request, reviews=[review])
    assert api.approve_pull_request.call_count == 1
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_ignore_closed_merged_prs() -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    Kodiak should only approve open PRs (not merged or closed).
    """
    for pull_request_state in (PullRequestState.CLOSED, PullRequestState.MERGED):
        mergeable = create_mergeable()
        api = create_api()
        config = create_config()
        pull_request = create_pull_request()
        config.approve.auto_approve_usernames = ["dependency-updater"]
        pull_request.author.login = "dependency-updater"
        pull_request.state = pull_request_state
        await mergeable(api=api, config=config, pull_request=pull_request, reviews=[])
        assert api.approve_pull_request.call_count == 0
        assert api.set_status.call_count == 0
        assert api.queue_for_merge.call_count == 0
        assert (
            api.dequeue.call_count == 1
        ), "dequeue because the PR is closed. This isn't related to this test."
        assert api.merge.call_count == 0
        assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_ignore_draft_pr() -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    Kodiak should not approve draft PRs.
    """
    mergeable = create_mergeable()
    config = create_config()
    pull_request_via_merge_state_status = create_pull_request()
    pull_request_via_is_draft = create_pull_request()
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request_via_is_draft.author.login = "dependency-updater"
    pull_request_via_merge_state_status.author.login = "dependency-updater"

    pull_request_via_is_draft.isDraft = True
    # configure mergeStateStatus.DRAFT instead of isDraft
    pull_request_via_merge_state_status.mergeStateStatus = MergeStateStatus.DRAFT

    for pull_request in (
        pull_request_via_is_draft,
        pull_request_via_merge_state_status,
    ):
        api = create_api()
        await mergeable(api=api, config=config, pull_request=pull_request, reviews=[])
        assert api.approve_pull_request.call_count == 0
        assert api.set_status.call_count == 1
        assert (
            "cannot merge (pull request is in draft state)"
            in api.set_status.calls[0]["msg"]
        )
        assert api.queue_for_merge.call_count == 0
        assert api.dequeue.call_count == 1
        assert api.merge.call_count == 0
        assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_missing_subscription() -> None:
    """
    If a subscription is missing we should not raise the paywall. The web_api
    system will set a subscription blocker if active users exceed the limit.
    """
    mergeable = create_mergeable()
    api = create_api()
    await mergeable(
        api=api,
        repository=RepoInfo(
            merge_commit_allowed=True,
            rebase_merge_allowed=True,
            squash_merge_allowed=True,
            delete_branch_on_merge=False,
            is_private=True,
        ),
        subscription=None,
    )

    assert api.queue_for_merge.call_count == 1
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.approve_pull_request.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_subscription_blocker() -> None:
    """
    If an account has a subscription_blocker we should display the paywall.
    """
    mergeable = create_mergeable()
    api = create_api()
    await mergeable(
        api=api,
        repository=RepoInfo(
            merge_commit_allowed=True,
            rebase_merge_allowed=True,
            squash_merge_allowed=True,
            delete_branch_on_merge=False,
            is_private=True,
        ),
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
        ),
    )
    assert api.set_status.call_count == 1
    assert (
        "💳 subscription: usage has exceeded licensed seats"
        in api.set_status.calls[0]["msg"]
    )

    assert api.queue_for_merge.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_public_repository() -> None:
    """
    Public repositories should never see a paywall.
    """
    for subscription in (
        None,
        Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
        ),
    ):
        api = create_api()
        mergeable = create_mergeable()
        await mergeable(
            api=api,
            repository=RepoInfo(
                merge_commit_allowed=True,
                rebase_merge_allowed=True,
                squash_merge_allowed=True,
                delete_branch_on_merge=False,
                is_private=False,
            ),
            subscription=subscription,
        )
        assert api.queue_for_merge.call_count == 1

        assert api.approve_pull_request.call_count == 0
        assert api.dequeue.call_count == 0
        assert api.merge.call_count == 0
        assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_missing_env(mocker: Any) -> None:
    """
    If the environment variable is disabled we should not throw up the paywall.
    """
    mergeable = create_mergeable()
    api = create_api()
    mocker.patch("kodiak.evaluation.app_config.SUBSCRIPTIONS_ENABLED", False)
    await mergeable(
        api=api,
        repository=RepoInfo(
            merge_commit_allowed=True,
            rebase_merge_allowed=True,
            squash_merge_allowed=True,
            delete_branch_on_merge=False,
            is_private=True,
        ),
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
        ),
    )
    assert api.queue_for_merge.call_count == 1

    assert api.approve_pull_request.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_subscription_expired() -> None:
    """
    When a subscription is expired we should not merge a pull request.

    This only applies to private repositories because Kodiak is free on public
    repositories.
    """
    api = create_api()
    mergeable = create_mergeable()
    repository = create_repo_info()
    repository.is_private = True
    await mergeable(
        api=api,
        repository=repository,
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SubscriptionExpired(),
        ),
    )

    assert api.set_status.call_count == 1
    assert "subscription expired" in api.set_status.calls[0]["msg"]

    assert api.dequeue.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_trial_expired() -> None:
    """
    When a trial has expired we should not act on a pull request.
    """
    api = create_api()
    mergeable = create_mergeable()
    repository = create_repo_info()
    repository.is_private = True
    await mergeable(
        api=api,
        repository=repository,
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=TrialExpired(),
        ),
    )

    assert api.set_status.call_count == 1
    assert "trial ended" in api.set_status.calls[0]["msg"]

    assert api.dequeue.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_seats_exceeded() -> None:
    """
    When an account has exceeded their seat usage they should hit the paywall.
    """
    api = create_api()
    mergeable = create_mergeable()
    repository = create_repo_info()
    repository.is_private = True
    await mergeable(
        api=api,
        repository=repository,
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SeatsExceeded(allowed_user_ids=[]),
        ),
    )

    assert api.set_status.call_count == 1
    assert "exceeded licensed seats" in api.set_status.calls[0]["msg"]

    assert api.dequeue.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_seats_exceeded_allowed_user() -> None:
    """
    Users that have a seat should be allowed to continue using Kodiak even if
    the subscription has exceeded limits.

    When an account exceeds it's seat limit we raise the "seats_exceeded"
    paywall. However we also record the user ids that occupy a seat and should
    be allowed to continue using Kodiak. Any user on this list will be able to
    use Kodiak while any others will hit a paywall.
    """
    api = create_api()
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    repository = create_repo_info()
    pull_request.author.databaseId = 234234234
    repository.is_private = True
    await mergeable(
        api=api,
        pull_request=pull_request,
        repository=repository,
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker=SeatsExceeded(
                allowed_user_ids=[pull_request.author.databaseId]
            ),
        ),
    )

    assert api.dequeue.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.queue_for_merge.call_count == 1
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_merge_pull_request_api_exception() -> None:
    """
    If we attempt to merge a pull request but get an internal server error from
    GitHub we should leave a comment and disable the bot via the
    `disable_bot_label` label. This will help prevent the bot from running out
    of control.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    api.merge.raises = GitHubApiInternalServerError
    config.merge.require_automerge_label = False

    await mergeable(api=api, config=config, merging=True)
    assert api.set_status.call_count == 2
    assert "attempting to merge PR" in api.set_status.calls[0]["msg"]
    assert "Cannot merge due to GitHub API failure" in api.set_status.calls[1]["msg"]
    assert api.merge.call_count == 1
    assert api.dequeue.call_count == 1
    assert api.remove_label.call_count == 0
    assert api.add_label.call_count == 1
    assert api.add_label.calls[0]["label"] == config.disable_bot_label
    assert api.create_comment.call_count == 1
    assert (
        "This PR could not be merged because the GitHub API returned an internal server"
        in api.create_comment.calls[0]["body"]
    )
    assert (
        f"remove the `{config.disable_bot_label}` label"
        in api.create_comment.calls[0]["body"]
    )

    assert api.queue_for_merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_merge_failure_label() -> None:
    """
    Kodiak should take no action on a pull request when
    disable_bot_label is applied. This is similar to missing an
    automerge label when require_automerge_label is enabled.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()
    pull_request = create_pull_request()

    config.merge.require_automerge_label = False
    pull_request.labels = [config.disable_bot_label]

    await mergeable(api=api, config=config, pull_request=pull_request, merging=True)
    assert api.set_status.call_count == 1
    assert "kodiak disabled by disable_bot_label" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    assert api.merge.call_count == 0
    assert api.remove_label.call_count == 0
    assert api.add_label.call_count == 0
    assert api.create_comment.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_priority_merge_label() -> None:
    """
    When a PR has merge.priority_merge_label, we should place it at the front of
    the merge queue.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    config.merge.priority_merge_label = "merge this PR stat!"

    # check default case.
    await mergeable(api=api, config=config)
    assert api.set_status.call_count == 1
    assert "enqueued" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert (
        api.queue_for_merge.calls[0]["first"] is False
    ), "by default we should place PR at end of queue (first=False)"

    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 0

    # check merge.priority_merge_label.
    api = create_api()
    pull_request = create_pull_request()
    pull_request.labels.append(config.merge.priority_merge_label)
    await mergeable(api=api, config=config, pull_request=pull_request)

    assert api.set_status.call_count == 1
    assert "enqueued" in api.set_status.calls[0]["msg"]

    assert api.queue_for_merge.call_count == 1
    assert (
        api.queue_for_merge.calls[0]["first"] is True
    ), "when merge.priority_merge_label is configured we should place PR at front of queue"

    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 0
