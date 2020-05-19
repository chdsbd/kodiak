import logging
from datetime import datetime, timedelta
from typing import Any, List, Mapping, Optional, Tuple, Union

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
    PollForever,
    RetryForSkippableChecks,
    GitHubApiInternalServerError,
)
from kodiak.evaluation import PRAPI, MergeBody, get_merge_body
from kodiak.evaluation import mergeable as mergeable_func
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
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
    PullRequestState,
    PushAllowance,
    PushAllowanceActor,
    RepoInfo,
    StatusContext,
    StatusState,
    Subscription,
)

log = logging.getLogger(__name__)


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
    raises: Optional[Exception] = None

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
    return_value: Optional[int] = None

    async def __call__(self) -> Optional[int]:
        self.log_call(dict())
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


def create_config_str() -> str:
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


def create_config_path() -> str:
    return "master:.kodiak.toml"


@pytest.fixture
def pull_request() -> PullRequest:
    return PullRequest(
        id="FDExOlB1bGxSZXX1ZXN0MjgxODQ0Nzg7",
        number=142,
        author=PullRequestAuthor(
            login="barry", name="Barry Berkman", databaseId=828352, type="User"
        ),
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
        url="https://github.com/example_org/example_repo/pull/65",
    )


def create_pull_request() -> PullRequest:
    return PullRequest(
        id="FDExOlB1bGxSZXX1ZXN0MjgxODQ0Nzg7",
        number=142,
        author=PullRequestAuthor(
            login="barry", name="Barry Berkman", databaseId=828352, type="User"
        ),
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
        url="https://github.com/example_org/example_repo/pull/65",
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
        restrictsPushes=False,
        pushAllowances=NodeListPushAllowance(nodes=[]),
    )


def create_branch_protection() -> BranchProtectionRule:
    return BranchProtectionRule(
        requiresApprovingReviews=True,
        requiredApprovingReviewCount=1,
        requiresStatusChecks=True,
        requiredStatusCheckContexts=["ci/api"],
        requiresStrictStatusChecks=True,
        requiresCommitSignatures=False,
        restrictsPushes=False,
        pushAllowances=NodeListPushAllowance(nodes=[]),
    )


@pytest.fixture
def review() -> PRReview:
    return PRReview(
        state=PRReviewState.APPROVED,
        createdAt=datetime(2015, 5, 25),
        author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
    )


def create_review() -> PRReview:
    return PRReview(
        state=PRReviewState.APPROVED,
        createdAt=datetime(2015, 5, 25),
        author=PRReviewAuthor(login="ghost", permission=Permission.WRITE),
    )


@pytest.fixture
def context() -> StatusContext:
    return StatusContext(context="ci/api", state=StatusState.SUCCESS)


def create_context() -> StatusContext:
    return StatusContext(context="ci/api", state=StatusState.SUCCESS)


@pytest.fixture
def check_run() -> CheckRun:
    return CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)


def create_check_run() -> CheckRun:
    return CheckRun(name="WIP (beta)", conclusion=CheckConclusionState.SUCCESS)


@pytest.fixture
def review_request() -> PRReviewRequest:
    return PRReviewRequest(name="ghost")


def create_review_request() -> PRReviewRequest:
    return PRReviewRequest(name="ghost")


def test_config_fixtures_equal(config_str: str, config: V1) -> None:
    assert config == V1.parse_toml(config_str)


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
    cfg.merge.method = MergeMethod.squash
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
        valid_signature: bool = False,
        valid_merge_methods: List[MergeMethod] = [MergeMethod.squash],
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


async def mergeable(
    api: PRAPI,
    config: Union[V1, pydantic.ValidationError, TomlDecodeError],
    config_str: str,
    config_path: str,
    pull_request: PullRequest,
    branch_protection: Optional[BranchProtectionRule],
    review_requests: List[PRReviewRequest],
    reviews: List[PRReview],
    contexts: List[StatusContext],
    check_runs: List[CheckRun],
    valid_signature: bool,
    valid_merge_methods: List[MergeMethod],
    merging: bool,
    is_active_merge: bool,
    skippable_check_timeout: int,
    api_call_retry_timeout: int,
    api_call_retry_method_name: Optional[str],
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


@pytest.mark.asyncio
async def test_mergeable_abort_is_active_merge() -> None:
    """
    If we set is_active_merge, that means that in the merge queue the current PR
    is being updated/merged, so in the frontend we don't want to act on the PR
    because the PR is being handled.
    """
    api = create_api()
    mergeable = create_mergeable()
    api.queue_for_merge.return_value = 4
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
    api.queue_for_merge.return_value = 3
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
    assert api.set_status.call_count == 0
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
async def test_mergeable_blacklist_title_regex() -> None:
    """
    block merge if title regex matches pull request
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
    assert "matches blacklist_title_regex" in api.set_status.calls[0]["msg"]

    # verify we haven't tried to update/merge the PR
    assert api.update_branch.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


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
    api.queue_for_merge.return_value = 5

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
    assert "enqueued for merge (position=6th)" in api.set_status.calls[0]["msg"]

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
    api.queue_for_merge.return_value = 3

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
    api.queue_for_merge.return_value = 3
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
async def test_mergeable_optimistic_update_wait_for_checks(
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
    test merge.optimistic_updates when we don't need a branch update. Since merge.optimistic_updates is enabled we should wait_for_checks
    """
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
            config_str=config_str,
            config_path=config_path,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
            is_active_merge=False,
            skippable_check_timeout=5,
            api_call_retry_timeout=5,
            api_call_retry_method_name=None,
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
async def test_mergeable_wait_for_checks(
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
    test merge.optimistic_updates when we don't have checks to wait for. Since merge.optimistic_updates is disabled we should update the branch.
    """
    config.merge.optimistic_updates = False
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True

    with pytest.raises(PollForever):
        await mergeable(
            api=api,
            config=config,
            config_str=config_str,
            config_path=config_path,
            pull_request=pull_request,
            branch_protection=branch_protection,
            review_requests=[],
            reviews=[review],
            check_runs=[check_run],
            contexts=[context],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
            is_active_merge=False,
            skippable_check_timeout=5,
            api_call_retry_timeout=5,
            api_call_retry_method_name=None,
            #
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
async def test_mergeable_unknown_merge_blockage(
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
    Test how kodiak behaves when we cannot figure out why a PR is blocked.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        check_runs=[check_run],
        contexts=[context],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )

    assert api.set_status.call_count == 1
    assert api.dequeue.call_count == 1
    assert api.update_branch.call_count == 0
    assert "Merging blocked by GitHub" in api.set_status.calls[0]["msg"]
    # verify we haven't tried to merge the PR
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_prioritize_ready_to_merge(
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
    If we enabled merge.prioritize_ready_to_merge, then if a PR is ready to merge when it reaches Kodiak, we merge it immediately. merge.prioritize_ready_to_merge is basically the sibling of merge.update_branch_immediately.
    """
    config.merge.prioritize_ready_to_merge = True

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        reviews=[review],
        check_runs=[check_run],
        contexts=[context],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )

    assert api.set_status.call_count == 1
    assert "attempting to merge PR (merging)" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 1

    # verify we haven't tried to merge the PR
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_merge(
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
    If we're merging we should call api.merge
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
        check_runs=[check_run],
        contexts=[context],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        #
        merging=True,
    )

    assert api.set_status.call_count == 1
    assert "attempting to merge PR (merging)" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 1
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_queue_for_merge_no_position(
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
    If we're attempting to merge from the frontend we should place the PR on the queue.
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
        check_runs=[check_run],
        contexts=[context],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )

    assert api.set_status.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.update_branch.call_count == 0
    assert api.merge.call_count == 0
    assert api.queue_for_merge.call_count == 1


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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_need_update(
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
    When a PR isn't in the queue but needs an update we should enqueue it for merge.
    """
    api.queue_for_merge.return_value = 3
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_failing_reviews(
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
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 2
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
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
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
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
async def test_regression_mishandling_multiple_reviews_okay_reviews(
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
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    api.queue_for_merge.return_value = 3

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
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
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_okay_dismissed_reviews(
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
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    api.queue_for_merge.return_value = 3

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
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
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_regression_mishandling_multiple_reviews_okay_non_member_reviews(
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
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresApprovingReviews = True
    branch_protection.requiredApprovingReviewCount = 1
    first_review_date = datetime(2010, 5, 15)
    latest_review_date = first_review_date + timedelta(minutes=20)
    api.queue_for_merge.return_value = 3

    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
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
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 0
    assert api.queue_for_merge.call_count == 1

    # verify we haven't tried to update/merge the PR
    assert api.merge.called is False
    assert api.update_branch.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge(
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
    merge.do_not_merge should disable merging a PR.
    """
    config.merge.do_not_merge = True
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.called is True
    assert "okay to merge" in api.set_status.calls[0]["msg"]

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge_behind_no_update_immediately(
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
    merge.do_not_merge without merge.update_branch_immediately means that any PR
    behind target will never get updated. We should display a warning about
    this.
    """
    config.merge.do_not_merge = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND

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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
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
async def test_mergeable_do_not_merge_with_update_branch_immediately_no_update(
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
    merge.do_not_merge is only useful with merge.update_branch_immediately, 
    Test when PR doesn't need update.
    """
    config.merge.do_not_merge = True
    config.merge.update_branch_immediately = True
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.called is True
    assert "okay to merge" in api.set_status.calls[0]["msg"]

    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_do_not_merge_with_update_branch_immediately_waiting_for_checks(
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
    merge.do_not_merge is only useful with merge.update_branch_immediately, 
    Test when PR doesn't need update but is waiting for checks to finish.
    """
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
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
async def test_mergeable_do_not_merge_with_update_branch_immediately_need_update(
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
    merge.do_not_merge is only useful with merge.update_branch_immediately, 
    Test when PR needs update.
    """
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    config.merge.do_not_merge = True
    config.merge.update_branch_immediately = True
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )

    assert api.update_branch.called is True
    assert api.set_status.called is True
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.called is False
    assert api.merge.called is False


@pytest.mark.asyncio
async def test_mergeable_api_call_retry_timeout(
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
    if we enounter too many errors calling GitHub api_call_retry_timeout will be zero. we should notify users via a status check.
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
        is_active_merge=False,
        skippable_check_timeout=5,
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
async def test_mergeable_api_call_retry_timeout_missing_method(
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
    if we enounter too many errors calling GitHub api_call_retry_timeout will be zero. we should notify users via a status check.

    This shouldn't really be possible in reality, but this is a test where the method name is None but the timeout is zero.
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
        is_active_merge=False,
        skippable_check_timeout=5,
        #
        api_call_retry_timeout=0,
        api_call_retry_method_name=None,
    )

    assert api.set_status.called is True
    assert "problem contacting GitHub API" in api.set_status.calls[0]["msg"]
    assert api.update_branch.called is False
    assert api.queue_for_merge.called is False
    assert api.merge.called is False
    assert api.queue_for_merge.called is False


@pytest.mark.asyncio
async def test_mergeable_skippable_check_timeout(
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
    we wait for skippable checks when merging because it takes time for check statuses to be sent and acknowledged by GitHub. We time out after some time because skippable checks are likely to never complete. In this case we want to notify the user of this via status check.
    """
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
        is_active_merge=False,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        #
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


def test_pr_get_merge_body_full(pull_request: PullRequest) -> None:
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    title=MergeTitleStyle.pull_request_title,
                    body=MergeBodyStyle.pull_request_body,
                    include_pr_number=True,
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_title=pull_request.title + f" (#{pull_request.number})",
        commit_message=pull_request.body,
    )
    assert expected == actual


def test_pr_get_merge_body_empty(pull_request: PullRequest) -> None:
    actual = get_merge_body(
        V1(version=1, merge=Merge(method=MergeMethod.squash)), pull_request
    )
    expected = MergeBody(merge_method="squash")
    assert actual == expected


def test_get_merge_body_strip_html_comments(pull_request: PullRequest) -> None:
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, strip_html_comments=True
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(merge_method="squash", commit_message="hello world")
    assert actual == expected


def test_get_merge_body_empty(pull_request: PullRequest) -> None:
    pull_request.body = "hello world"
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(body=MergeBodyStyle.empty),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(merge_method="squash", commit_message="")
    assert actual == expected


def test_get_merge_body_includes_pull_request_url(pull_request: PullRequest) -> None:
    """
    Ensure that when the appropriate config option is set, we include the
    pull request url in the commit message.
    """
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, include_pull_request_url=True
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65""",
    )
    assert actual == expected


def test_get_merge_body_includes_pull_request_url_with_coauthor(
    pull_request: PullRequest
) -> None:
    """
    Coauthor should appear after the pull request url
    """
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_url=True,
                    include_pull_request_author=True,
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65

Co-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>""",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_user(
    pull_request: PullRequest
) -> None:
    pull_request.body = "hello world"

    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.empty, include_pull_request_author=True
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="\n\nCo-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_bot(
    pull_request: PullRequest
) -> None:
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Bot"

    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry[bot] <828352+barry[bot]@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_mannequin(
    pull_request: PullRequest
) -> None:
    """
    Test case where actor is not a User and Bot to see how we handle weird cases.
    """
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Mannequin"

    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                ),
            ),
        ),
        pull_request,
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


@pytest.mark.asyncio
async def test_mergeable_update_username_blacklist(
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
    Kodiak should not update PR if user is blacklisted.
    """
    config.update.always = True
    config.update.blacklist_usernames = ["mr-test"]
    config.update.require_automerge_label = True
    pull_request.author.login = "mr-test"
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.FAILURE

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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.update_branch.call_count == 0
    assert api.set_status.call_count == 1
    assert (
        "not auto updating for update.blacklist_usernames"
        in api.set_status.calls[0]["msg"]
    )

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_username_blacklist_merging(
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
    When the PR is merging, Kodiak should ignore update.username_blacklist and
    update the PR as necessary for GitHub branch protections.
    """
    config.update.always = True
    config.update.blacklist_usernames = ["mr-test"]
    config.update.require_automerge_label = True
    pull_request.author.login = "mr-test"
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStatusChecks = True
    branch_protection.requiredStatusCheckContexts = ["ci/test-api"]
    check_run.name = "ci/test-api"
    check_run.conclusion = CheckConclusionState.SUCCESS

    with pytest.raises(PollForever):
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
            is_active_merge=False,
            skippable_check_timeout=5,
            api_call_retry_timeout=5,
            api_call_retry_method_name=None,
            #
            merging=True,
        )
    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_always(
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
    Kodiak should update PR even when failing requirements for merge
    """
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_always_require_automerge_label_missing_label(
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
    Kodiak should not update branch if update.require_automerge_label is True and we're missing the automerge label.
    """
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.update_branch.call_count == 0

    assert api.set_status.call_count == 1
    assert "missing automerge_label:" in api.set_status.calls[0]["msg"]
    assert api.dequeue.call_count == 1

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_always_no_require_automerge_label_missing_label(
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
    Kodiak should update branch if update.require_automerge_label is True and we're missing the automerge label.
    """
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.update_branch.call_count == 1
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert "branch updated because" in api.set_status.calls[0]["markdown_content"]

    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_passing_update_always_enabled(
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
    Test happy case with update.always enabled. We should shouldn't see any
    difference with update.always enabled.
    """
    config.update.always = True
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_update_always_enabled_merging_behind_pull_request(
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
    When we're merging with update.always enabled we don't want to update the
    branch using our update.always logic. We want to update using our merging
    logic so we trigger the PollForever exception necessary to continue our
    merge loop. If we used the update.always logic we'd eject a PR if it became
    out of sync during merge.
    """
    config.update.always = True
    pull_request.mergeStateStatus = MergeStateStatus.BEHIND
    branch_protection.requiresStrictStatusChecks = True

    with pytest.raises(PollForever):
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
            is_active_merge=False,
            skippable_check_timeout=5,
            api_call_retry_timeout=5,
            api_call_retry_method_name=None,
            #
            merging=True,
        )
    assert api.set_status.call_count == 1
    assert "updating branch" in api.set_status.calls[0]["msg"]
    assert api.update_branch.call_count == 1
    assert api.queue_for_merge.call_count == 0
    assert api.merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve(
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
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.
    """
    api.queue_for_merge.return_value = 3
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        #
        reviews=[],
    )
    assert api.approve_pull_request.call_count == 1
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_existing_approval(
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
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    If we have an existing, valid approval, we should not add another.
    """
    api.queue_for_merge.return_value = 3
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    review.author.login = "kodiak-test-app"
    review.state = PRReviewState.APPROVED
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.approve_pull_request.call_count == 0
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_old_approval(
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
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    If we have a dismissed approval, we should add a fresh one.
    """
    api.queue_for_merge.return_value = 3
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    review.author.login = "kodiak-test-app"
    review.state = PRReviewState.DISMISSED
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
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
    )
    assert api.approve_pull_request.call_count == 1
    assert api.set_status.call_count == 1
    assert "enqueued for merge (position=4th)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 1
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.parametrize(
    "pull_request_state", (PullRequestState.CLOSED, PullRequestState.MERGED)
)
@pytest.mark.asyncio
async def test_mergeable_auto_approve_ignore_closed_merged_prs(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
    pull_request_state: PullRequestState,
) -> None:
    """
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    Kodiak should only approve open PRs (not merged or closed).
    """
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    pull_request.state = pull_request_state
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        #
        reviews=[],
    )
    assert api.approve_pull_request.call_count == 0
    assert api.set_status.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert (
        api.dequeue.call_count == 1
    ), "dequeue because the PR is closed. This isn't related to this test."
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_auto_approve_ignore_draft_pr(
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
    If a PR is opened by a user on the `approve.auto_approve_usernames` list Kodiak should approve the PR.

    Kodiak should not approve draft PRs.
    """
    config.approve.auto_approve_usernames = ["dependency-updater"]
    pull_request.author.login = "dependency-updater"
    pull_request.mergeStateStatus = MergeStateStatus.DRAFT
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        #
        reviews=[],
    )
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
async def test_mergeable_paywall_missing_subscription(
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
    If a subscription is missing we should not raise the paywall. The web_api
    system will set a subscription blocker if active users exceed the limit.
    """
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
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
    assert api.set_status.call_count == 0
    assert api.approve_pull_request.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_subscription_blocker(
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
    If an account has a subscription_blocker we should display the paywall.
    """
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        repository=RepoInfo(
            merge_commit_allowed=True,
            rebase_merge_allowed=True,
            squash_merge_allowed=True,
            delete_branch_on_merge=False,
            is_private=True,
        ),
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker="seats_exceeded",
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
async def test_mergeable_paywall_public_repository(
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
    Public repositories should never see a paywall.
    """
    for index, subscription in enumerate(
        (
            None,
            Subscription(
                account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
                subscription_blocker="seats_exceeded",
            ),
        )
    ):
        await mergeable(
            api=api,
            config=config,
            config_str=config_str,
            config_path=config_path,
            pull_request=pull_request,
            branch_protection=branch_protection,
            reviews=[review],
            review_requests=[],
            contexts=[context],
            check_runs=[check_run],
            valid_signature=False,
            valid_merge_methods=[MergeMethod.squash],
            merging=False,
            is_active_merge=False,
            skippable_check_timeout=5,
            api_call_retry_timeout=5,
            api_call_retry_method_name=None,
            repository=RepoInfo(
                merge_commit_allowed=True,
                rebase_merge_allowed=True,
                squash_merge_allowed=True,
                delete_branch_on_merge=False,
                is_private=False,
            ),
            subscription=subscription,
        )
        assert api.queue_for_merge.call_count == index + 1

        assert api.approve_pull_request.call_count == 0
        assert api.dequeue.call_count == 0
        assert api.merge.call_count == 0
        assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_paywall_missing_env(
    api: MockPrApi,
    config: V1,
    config_path: str,
    config_str: str,
    pull_request: PullRequest,
    branch_protection: BranchProtectionRule,
    review: PRReview,
    context: StatusContext,
    check_run: CheckRun,
    mocker: Any,
) -> None:
    """
    If the environment variable is disabled we should not throw up the paywall.
    """
    mocker.patch("kodiak.evaluation.app_config.SUBSCRIPTIONS_ENABLED", False)
    await mergeable(
        api=api,
        config=config,
        config_str=config_str,
        config_path=config_path,
        pull_request=pull_request,
        branch_protection=branch_protection,
        reviews=[review],
        review_requests=[],
        contexts=[context],
        check_runs=[check_run],
        valid_signature=False,
        valid_merge_methods=[MergeMethod.squash],
        merging=False,
        is_active_merge=False,
        skippable_check_timeout=5,
        api_call_retry_timeout=5,
        api_call_retry_method_name=None,
        repository=RepoInfo(
            merge_commit_allowed=True,
            rebase_merge_allowed=True,
            squash_merge_allowed=True,
            delete_branch_on_merge=False,
            is_private=True,
        ),
        subscription=Subscription(
            account_id="cc5674b3-b53c-4c4e-855d-7b3c52b8325f",
            subscription_blocker="seats_exceeded",
        ),
    )
    assert api.queue_for_merge.call_count == 1

    assert api.approve_pull_request.call_count == 0
    assert api.dequeue.call_count == 0
    assert api.merge.call_count == 0
    assert api.update_branch.call_count == 0


@pytest.mark.asyncio
async def test_mergeable_merge_pull_request_api_exception() -> None:
    """
    If we attempt to merge a pull request but get an internal server error from
    GitHub we should remove the automerge label to disable the bot and leave a
    comment.
    """
    api = create_api()
    mergeable = create_mergeable()
    config = create_config()

    api.merge.raises = GitHubApiInternalServerError

    await mergeable(api=api, config=config, merging=True)
    assert api.set_status.call_count == 2
    assert "attempting to merge PR" in api.set_status.calls[0]["msg"]
    assert "Cannot merge due to GitHub API failure" in api.set_status.calls[1]["msg"]
    assert api.merge.call_count == 1
    assert api.dequeue.call_count == 1
    assert api.remove_label.call_count == 1
    assert api.remove_label.calls[0]["label"] == config.merge.automerge_label
    assert api.create_comment.call_count == 1
    assert (
        "This PR could not be merged because the GitHub API returned an internal server"
        in api.create_comment.calls[0]["body"]
    )
    assert (
        f"re-add the `{config.merge.automerge_label}` label"
        in api.create_comment.calls[0]["body"]
    )

    assert api.queue_for_merge.call_count == 0
    assert api.update_branch.call_count == 0
