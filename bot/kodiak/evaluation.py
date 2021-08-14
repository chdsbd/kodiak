from __future__ import annotations

import asyncio
import textwrap
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Dict, List, MutableMapping, Optional, Sequence, Set, Union

import inflection
import pydantic
import rure as re
import structlog
import toml
from typing_extensions import Protocol

from kodiak import app_config, config, messages
from kodiak.assertions import assert_never
from kodiak.config import (
    DEFAULT_TITLE_REGEX,
    UNSET_TITLE_REGEX,
    V1,
    BodyText,
    MergeBodyStyle,
    MergeMethod,
    MergeTitleStyle,
)
from kodiak.dependencies import dep_version_from_title
from kodiak.errors import (
    GitHubApiInternalServerError,
    PollForever,
    RetryForSkippableChecks,
)
from kodiak.messages import (
    APICallRetry,
    get_markdown_for_api_call_errors,
    get_markdown_for_config,
    get_markdown_for_paywall,
    get_markdown_for_push_allowance_error,
)
from kodiak.queries import (
    BranchProtectionRule,
    CheckConclusionState,
    CheckRun,
    Commit,
    MergeableState,
    MergeStateStatus,
    Permission,
    PRReview,
    PRReviewRequest,
    PRReviewState,
    PullRequest,
    PullRequestCommitUser,
    PullRequestReviewDecision,
    PullRequestState,
    PushAllowance,
    RepoInfo,
    SeatsExceeded,
    StatusContext,
    StatusState,
    Subscription,
    SubscriptionExpired,
    TrialExpired,
)
from kodiak.text import strip_html_comments_from_markdown

# TODO(chdsbd): We could make an API request to `/app` on start to get this information, but this is pretty simple.
KODIAK_LOGIN = app_config.GITHUB_APP_NAME

logger = structlog.get_logger()


def get_body_content(
    *,
    body_type: BodyText,
    strip_html_comments: bool,
    cut_body_before: str,
    cut_body_after: str,
    pull_request: PullRequest,
) -> str:
    if body_type is BodyText.markdown:
        body = pull_request.body
        if cut_body_before != "":
            start_index = body.find(cut_body_before)
            if start_index != -1:
                body = body[start_index:]
        if cut_body_after != "":
            end_index = body.find(cut_body_after)
            if end_index != -1:
                body = body[: end_index + len(cut_body_after)]
        if strip_html_comments:
            return strip_html_comments_from_markdown(body)
        return body
    if body_type is BodyText.plain_text:
        return pull_request.bodyText
    if body_type is BodyText.html:
        return pull_request.bodyHTML
    assert_never(body_type)


EMPTY_STRING = ""


@dataclass
class CommitAuthorName:
    name: str
    login: str


def get_coauthor_trailer(
    *, user_id: int, login: str, name: Optional[str], type: str
) -> str:
    """
    Build a coauthor trailer given user information.
    """
    display_name = login
    display_login = login
    if type == "Bot":
        # the GitHub GraphQL API returns bot names without the `[bot]` suffix.
        display_name += "[bot]"
        display_login += "[bot]"
    if name:
        display_name = name

    # GitHub does not allow our GitHub App to view the email addresses of
    # pull request authors, so we generate a noreply GitHub email address
    # instead which works the same for the GitHub UI.
    author_email = f"{user_id}+{display_login}@users.noreply.github.com"
    return f"Co-authored-by: {display_name} <{author_email}>"


def get_coauthor_trailers(
    *,
    coauthors: List[PullRequestCommitUser],
    include_pull_request_author: bool,
    pull_request_author_id: int,
) -> List[str]:
    """
    Deduplicate coauthors and convert to strings.
    """
    coauthor_trailers = []
    deduped_coauthors: Dict[PullRequestCommitUser, bool] = {}
    for dupe_coauthor in coauthors:
        deduped_coauthors[dupe_coauthor] = True

    for coauthor in deduped_coauthors:
        if coauthor.databaseId is None:
            continue
        if (
            not include_pull_request_author
            and coauthor.databaseId == pull_request_author_id
        ):
            continue

        coauthor_trailers.append(
            get_coauthor_trailer(
                user_id=coauthor.databaseId,
                login=coauthor.login,
                name=coauthor.name,
                type=coauthor.type,
            )
        )
    return coauthor_trailers


@dataclass
class MergeBody:
    merge_method: str
    commit_title: Optional[str] = None
    commit_message: Optional[str] = None


def get_merge_body(
    config: V1,
    merge_method: MergeMethod,
    pull_request: PullRequest,
    commits: List[Commit],
) -> MergeBody:
    """
    Get merge options for a pull request to call GitHub API.
    """
    merge_body = MergeBody(merge_method=merge_method)
    if config.merge.message.body == MergeBodyStyle.pull_request_body:
        body = get_body_content(
            body_type=config.merge.message.body_type,
            strip_html_comments=config.merge.message.strip_html_comments,
            cut_body_before=config.merge.message.cut_body_before,
            cut_body_after=config.merge.message.cut_body_after,
            pull_request=pull_request,
        )
        merge_body.commit_message = body
    if config.merge.message.body == MergeBodyStyle.empty:
        merge_body.commit_message = EMPTY_STRING
    if config.merge.message.title == MergeTitleStyle.pull_request_title:
        merge_body.commit_title = pull_request.title
    if config.merge.message.include_pr_number and merge_body.commit_title is not None:
        merge_body.commit_title += f" (#{pull_request.number})"

    # MergeBodyStyle.github_default overrides these settings so we can ensure that GitHub generates the commit body.
    if config.merge.message.body in (
        MergeBodyStyle.pull_request_body,
        MergeBodyStyle.empty,
    ):
        if config.merge.message.include_pull_request_url:
            if merge_body.commit_message is None:
                merge_body.commit_message = pull_request.url
            else:
                merge_body.commit_message += "\n\n" + pull_request.url

        # we share coauthor logic between include_pull_request_author and
        # include_coauthors.
        coauthors = []  # type: List[PullRequestCommitUser]
        if config.merge.message.include_pull_request_author:
            coauthors.append(
                PullRequestCommitUser(
                    login=pull_request.author.login,
                    databaseId=pull_request.author.databaseId,
                    name=pull_request.author.name,
                    type=pull_request.author.type,
                )
            )
        if config.merge.message.include_coauthors:
            for commit in commits:
                if (
                    # only use commits that have identified authors.
                    commit.author is None
                    or commit.author.user is None
                    # ignore merge commits. They will have more than one parent.
                    or commit.parents.totalCount > 1
                ):
                    continue
                coauthors.append(commit.author.user)

        coauthor_trailers = get_coauthor_trailers(
            coauthors=coauthors,
            include_pull_request_author=config.merge.message.include_pull_request_author,
            pull_request_author_id=pull_request.author.databaseId,
        )

        if coauthor_trailers:
            trailer_block = "\n".join(coauthor_trailers)
            if merge_body.commit_message:
                merge_body.commit_message += "\n\n" + trailer_block
            else:
                merge_body.commit_message = trailer_block

    return merge_body


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


def deduplicate_check_runs(check_runs: Iterable[CheckRun]) -> Iterable[CheckRun]:
    check_run_map = {check_run.name: check_run for check_run in check_runs}
    return check_run_map.values()


class PRAPI(Protocol):
    async def dequeue(self) -> None:
        ...

    async def requeue(self) -> None:
        ...

    async def set_status(
        self, msg: str, *, markdown_content: Optional[str] = None
    ) -> None:
        ...

    async def pull_requests_for_ref(self, ref: str) -> Optional[int]:
        ...

    async def delete_branch(self, branch_name: str) -> None:
        ...

    async def remove_label(self, label: str) -> None:
        ...

    async def add_label(self, label: str) -> None:
        ...

    async def create_comment(self, body: str) -> None:
        ...

    async def trigger_test_commit(self) -> None:
        ...

    async def merge(
        self,
        merge_method: str,
        commit_title: Optional[str],
        commit_message: Optional[str],
    ) -> None:
        ...

    async def update_ref(self, *, ref: str, sha: str) -> None:
        ...

    async def queue_for_merge(self, *, first: bool) -> Optional[int]:
        ...

    async def update_branch(self) -> None:
        ...

    async def approve_pull_request(self) -> None:
        ...


async def cfg_err(
    api: PRAPI, msg: str, *, markdown_content: Optional[str] = None
) -> None:
    await api.dequeue()
    await api.set_status(f"⚠️ config error ({msg})", markdown_content=markdown_content)


async def block_merge(api: PRAPI, pull_request: PullRequest, msg: str) -> None:
    await api.dequeue()
    await api.set_status(f"🛑 cannot merge ({msg})")


def missing_push_allowance(push_allowances: List[PushAllowance]) -> bool:
    for push_allowance in push_allowances:
        # a null databaseId indicates this is not a GitHub App.
        if push_allowance.actor.databaseId is None:
            continue
        if str(push_allowance.actor.databaseId) == str(app_config.GITHUB_APP_ID):
            return False
    return True


def get_paywall_status_for_blocker(
    pull_request: PullRequest,
    subscription_blocker: Union[SubscriptionExpired, TrialExpired, SeatsExceeded],
    log: structlog.BoundLogger,
) -> Optional[str]:
    if isinstance(subscription_blocker, SeatsExceeded):
        if pull_request.author.databaseId in subscription_blocker.allowed_user_ids:
            return None
        return "usage has exceeded licensed seats"
    if isinstance(subscription_blocker, TrialExpired):
        return "trial ended"
    if isinstance(subscription_blocker, SubscriptionExpired):
        return "subscription expired"
    log.warning("unexpected subscription_blocker %s ", subscription_blocker)
    return None


@dataclass
class BlockingTitleRegex:
    pattern: str
    config_key: str


def get_blocking_title_regex(config: config.V1) -> BlockingTitleRegex:
    """
    merge.blocking_title_regex takes priority over merge.blacklist_title_regex.

    If neither options are set we return the default regex.
    """
    # config.merge.blocking_title_regex takes priority.
    if config.merge.blocking_title_regex != UNSET_TITLE_REGEX:
        return BlockingTitleRegex(
            pattern=config.merge.blocking_title_regex,
            config_key="merge.blocking_title_regex",
        )
    if config.merge.blacklist_title_regex != UNSET_TITLE_REGEX:
        return BlockingTitleRegex(
            pattern=config.merge.blacklist_title_regex,
            config_key="merge.blacklist_title_regex",
        )
    # user hasn't set either options so we return the default.
    return BlockingTitleRegex(
        pattern=DEFAULT_TITLE_REGEX, config_key="merge.blocking_title_regex"
    )


# merge methods ordered by preference for selection.
MERGE_METHODS = (
    MergeMethod.merge,
    MergeMethod.squash,
    MergeMethod.rebase,
    # rebase_fast_forward is not included here since it is not configurable via
    # the GitHub UI. Kodiak users can manually specify rebase_fast_forward in
    # their configuration file.
)


class MergeMethodValue(pydantic.BaseModel):
    method: MergeMethod


class MergeMethodOverride(pydantic.BaseModel):
    """
    Parse the decoded toml value from merge method override.

    A well formed object to parse will look like the following:
        {"merge": {"method": "rebase"}}
    """

    merge: MergeMethodValue


def get_merge_method(
    cfg_merge_method: Optional[MergeMethod],
    valid_merge_methods: List[MergeMethod],
    labels: List[str],
    log: structlog.BoundLogger,
) -> MergeMethod:

    # parse merge.method override label
    # example: `kodiak: merge.method = "rebase"`
    for label in labels:
        if not label.startswith("kodiak:"):
            continue
        # we have an existing label "kodiak:disabled". This label will not parse
        # here and will be ignored.
        _start, _sep, maybe_config = label.partition("kodiak:")
        try:
            merge_method_override = MergeMethodOverride.parse_obj(
                toml.loads(maybe_config)
            )
        except (toml.TomlDecodeError, pydantic.ValidationError):
            continue
        return merge_method_override.merge.method

    if cfg_merge_method is not None:
        return cfg_merge_method

    # take the first valid merge method.
    for merge_method in MERGE_METHODS:
        if merge_method in valid_merge_methods:
            return merge_method

    # NOTE(chdsbd): I don't think the following code should be reachable in
    # production, but I don't want to blow things up with an assert.
    log.warning(
        "no merge methods selected.",
        cfg_merge_method=cfg_merge_method,
        valid_merge_methods=valid_merge_methods,
    )
    return MergeMethod.merge


async def mergeable(
    api: PRAPI,
    config: Union[config.V1, pydantic.ValidationError, toml.TomlDecodeError],
    config_str: str,
    config_path: str,
    pull_request: PullRequest,
    branch_protection: Optional[BranchProtectionRule],
    review_requests: List[PRReviewRequest],
    reviews: List[PRReview],
    contexts: List[StatusContext],
    check_runs: List[CheckRun],
    commits: List[Commit],
    valid_merge_methods: List[MergeMethod],
    repository: RepoInfo,
    merging: bool,
    is_active_merge: bool,
    skippable_check_timeout: int,
    api_call_retries_remaining: int,
    api_call_errors: Sequence[APICallRetry],
    subscription: Optional[Subscription],
    app_id: Optional[str] = None,
) -> None:
    # TODO(chdsbd): Use structlog bind_contextvars to automatically set useful context (install id, repo, pr number).
    log = logger.bind(number=pull_request.number, url=pull_request.url)
    # we set is_active_merge when the PR is being merged from the merge queue.
    # We don't want to clobber any statuses set by that system, so we take no
    # action. If the PR becomes ineligible for merging that logic will handle
    # it.

    # rebase_fast_forward isn't determined via the GitHub UI and is always
    # available.
    valid_merge_methods = [*valid_merge_methods, MergeMethod.rebase_fast_forward]

    async def set_status(msg: str, markdown_content: Optional[str] = None) -> None:
        # don't clobber statuses set via merge loop.
        if is_active_merge:
            return
        await api.set_status(msg, markdown_content=markdown_content)

    if not isinstance(config, V1):
        log.warning("problem fetching config")
        await set_status(
            '⚠️ Invalid configuration (Click "Details" for more info.)',
            markdown_content=get_markdown_for_config(
                config, config_str=config_str, git_path=config_path
            ),
        )
        await api.dequeue()
        return

    if api_call_retries_remaining == 0:
        log.warning("timeout reached for api calls to GitHub")
        if api_call_errors:
            first_error = api_call_errors[0]
            await set_status(
                f"⚠️ problem contacting GitHub API with method {first_error.api_name!r}",
                markdown_content=get_markdown_for_api_call_errors(
                    errors=api_call_errors
                ),
            )
        else:
            await set_status("⚠️ problem contacting GitHub API")
        return

    # if we have an app_id in the config then we only want to work on this repo
    # if our app_id from the environment matches the configuration.
    if config.app_id is not None and config.app_id != app_id:
        log.info("missing required app_id")
        await api.dequeue()
        return

    if branch_protection is None:
        await cfg_err(
            api, f"missing branch protection for baseRef: {pull_request.baseRefName!r}"
        )
        return

    merge_method = get_merge_method(
        cfg_merge_method=config.merge.method,
        valid_merge_methods=valid_merge_methods,
        log=log,
        labels=pull_request.labels,
    )

    if (
        branch_protection.requiresCommitSignatures
        and merge_method == MergeMethod.rebase
    ):
        await cfg_err(
            api,
            '"Require signed commits" branch protection is only supported with "squash" or "merge" commits. Rebase is not supported by GitHub.',
        )
        return

    if merge_method not in valid_merge_methods:
        valid_merge_methods_str = [method.value for method in valid_merge_methods]
        await cfg_err(
            api,
            f"configured merge.method {merge_method.value!r} is invalid. Valid methods for repo are {valid_merge_methods_str!r}",
        )
        return

    if (
        not config.merge.do_not_merge
        and branch_protection.restrictsPushes
        and missing_push_allowance(branch_protection.pushAllowances.nodes)
    ):
        await cfg_err(
            api,
            "push restriction branch protection setting is missing push allowance for Kodiak",
            markdown_content=get_markdown_for_push_allowance_error(
                branch_name=pull_request.baseRefName
            ),
        )
        return

    # we keep the configuration errors before the rest of the application logic
    # so configuration issues are surfaced as early as possible.

    if config.disable_bot_label in pull_request.labels:
        await api.dequeue()
        await api.set_status(
            f"🚨 kodiak disabled by disable_bot_label ({config.disable_bot_label}). Remove label to re-enable Kodiak."
        )
        return

    if (
        app_config.SUBSCRIPTIONS_ENABLED
        and repository.is_private
        and subscription is not None
        and subscription.subscription_blocker is not None
    ):
        # We only count private repositories in our usage calculations. A user
        # has an active subscription if a subscription exists in Redis and has
        # an empty subscription_blocker.
        #
        # We also ignore missing subscriptions. The web api will set
        # subscription blockers if usage exceeds limits.
        status_message = get_paywall_status_for_blocker(
            pull_request, subscription.subscription_blocker, log
        )
        if status_message is not None:
            await set_status(
                f"💳 subscription: {status_message}",
                markdown_content=get_markdown_for_paywall(),
            )
            return

    pull_request_labels = set(pull_request.labels)
    config_automerge_labels = (
        {config.merge.automerge_label}
        if isinstance(config.merge.automerge_label, str)
        else set(config.merge.automerge_label)
    )
    pull_request_automerge_labels = config_automerge_labels.intersection(
        pull_request_labels
    )
    has_automerge_label = len(pull_request_automerge_labels) > 0

    should_dependency_automerge = (
        pull_request.author.login in config.merge.automerge_dependencies.usernames
        and dep_version_from_title(pull_request.title)
        in config.merge.automerge_dependencies.versions
    )

    # we should trigger mergeability checks whenever we encounter UNKNOWN.
    #
    # I don't foresee conflicts with checking configuration errors,
    # `config.disable_bot_label`, and the paywall before this code.
    #
    # Previously we had an issue where this code wasn't being entered because
    # `merge.blocking_title_regex` was checked first. Which caused
    # `update.always` to not operate.
    if (
        pull_request.mergeable == MergeableState.UNKNOWN
        and pull_request.state == PullRequestState.OPEN
    ):
        # we need to trigger a test commit to fix this. We do that by calling
        # GET on the pull request endpoint.
        await api.trigger_test_commit()

        # queue the PR for evaluation again in case GitHub doesn't send another
        # webhook for the commit test.
        await api.requeue()

        # we don't want to abort the merge if we encounter this status check.
        # Just keep polling!
        if merging:
            raise PollForever

        return

    is_draft_pull_request = (
        pull_request.isDraft or pull_request.mergeStateStatus == MergeStateStatus.DRAFT
    )
    if (
        pull_request.author.login in config.approve.auto_approve_usernames
        and pull_request.state == PullRequestState.OPEN
        and not is_draft_pull_request
    ):
        # if the PR was created by an approve author and we have not previously
        # given an approval, approve the PR.
        sorted_reviews = sorted(reviews, key=lambda x: x.createdAt)
        kodiak_reviews = [
            review for review in sorted_reviews if review.author.login == KODIAK_LOGIN
        ]
        status = review_status(kodiak_reviews)
        if status != PRReviewState.APPROVED:
            await api.approve_pull_request()
        else:
            log.info("approval already exists, not adding another")

    need_branch_update = (
        branch_protection.requiresStrictStatusChecks
        and pull_request.mergeStateStatus == MergeStateStatus.BEHIND
    )
    update_always = config.update.always and (
        has_automerge_label or not config.update.require_automerge_label
    )
    has_autoupdate_label = config.update.autoupdate_label in pull_request_labels
    auto_update_enabled = update_always or has_autoupdate_label

    # Dequeue pull request if out-of-date and author in
    # `update.ignored_usernames`. We cannot update or merge it.
    #
    # If `update.autoupdate_label` is applied to the pull request, bypass
    # `update.ignored_usernames` and let the pull request update.
    if need_branch_update and not has_autoupdate_label:
        if pull_request.author.login in config.update.blacklist_usernames:
            await set_status(
                f"🛑 updates blocked by update.blacklist_usernames: {config.update.blacklist_usernames!r}",
                markdown_content="Apply the `update.autoupdate_label` label to enable updates for this pull request.",
            )
            await api.dequeue()
            return
        if pull_request.author.login in config.update.ignored_usernames:
            await set_status(
                f"🛑 updates blocked by update.ignored_usernames: {config.update.ignored_usernames!r}",
                markdown_content="Apply the `update.autoupdate_label` label to enable updates for this pull request.",
            )
            await api.dequeue()
            return

    if need_branch_update and not merging and auto_update_enabled:
        await set_status(
            "🔄 updating branch",
            markdown_content="branch updated because `update.always = true` is configured.",
        )
        await api.update_branch()
        return

    if (
        config.merge.require_automerge_label
        and not has_automerge_label
        and not should_dependency_automerge
    ):
        await block_merge(
            api,
            pull_request,
            f"missing automerge_label: {config.merge.automerge_label!r}",
        )
        return

    # We want users to get notified a merge conflict even if the PR matches a
    # WIP title via merge.blacklist_title_regex.
    if (
        pull_request.mergeStateStatus == MergeStateStatus.DIRTY
        or pull_request.mergeable == MergeableState.CONFLICTING
    ) and pull_request.state == PullRequestState.OPEN:
        await block_merge(api, pull_request, "merge conflict")
        # remove label if configured and send message
        if (
            config.merge.notify_on_conflict
            and config.merge.require_automerge_label
            and has_automerge_label
        ):
            automerge_label = config.merge.automerge_label
            await asyncio.gather(
                *[api.remove_label(label) for label in pull_request_automerge_labels]
            )
            body = textwrap.dedent(
                f"""
            This PR currently has a merge conflict. Please resolve this and then re-add the `{automerge_label}` label.
            """
            )
            await api.create_comment(body)
        return

    blacklist_labels = set(config.merge.blacklist_labels) & set(pull_request.labels)
    blocking_labels = set(config.merge.blocking_labels) & set(pull_request.labels)
    if blacklist_labels:
        await block_merge(
            api, pull_request, f"has blacklist_labels: {blacklist_labels!r}"
        )
        return
    if blocking_labels:
        await block_merge(
            api, pull_request, f"has merge.blocking_labels: {blocking_labels!r}"
        )
        return

    title_blocker = get_blocking_title_regex(config)

    if (
        title_blocker.pattern
        and re.search(title_blocker.pattern, pull_request.title) is not None
    ):
        await block_merge(
            api,
            pull_request,
            f"title matches {title_blocker.config_key}: {title_blocker.pattern!r}",
        )
        return

    if is_draft_pull_request:
        await block_merge(api, pull_request, "pull request is in draft state")
        return

    if config.merge.block_on_reviews_requested and review_requests:
        names = [r.name for r in review_requests]
        await block_merge(api, pull_request, f"reviews requested: {names!r}")
        return

    if pull_request.state == PullRequestState.MERGED:
        log.info(
            "pull request merged. config.merge.delete_branch_on_merge=%r",
            config.merge.delete_branch_on_merge,
        )
        await api.dequeue()
        if (
            not config.merge.delete_branch_on_merge
            or pull_request.isCrossRepository
            or repository.delete_branch_on_merge
        ):
            return
        pr_count = await api.pull_requests_for_ref(ref=pull_request.headRefName)
        # if we couldn't access the dependent PR count or we have dependent PRs
        # we will abort deleting this branch.
        if pr_count is None or pr_count > 0:
            log.info(
                "skipping branch deletion because of dependent PRs", pr_count=pr_count
            )
            return
        await api.delete_branch(branch_name=pull_request.headRefName)
        return

    if pull_request.state == PullRequestState.CLOSED:
        await api.dequeue()
        return

    if pull_request.mergeStateStatus == MergeStateStatus.UNSTABLE:
        # TODO(chdsbd): This status means that the pr is mergeable but has failing
        # status checks. we may want to handle this via config
        pass

    wait_for_checks = False
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
                    await block_merge(
                        api, pull_request, f"changes requested by {author_name!r}"
                    )
                    return
                # successful review
                if review_state == PRReviewState.APPROVED:
                    successful_reviews += 1
            # missing required review count
            if successful_reviews < branch_protection.requiredApprovingReviewCount:
                await block_merge(
                    api,
                    pull_request,
                    f"missing required reviews, have {successful_reviews!r}/{branch_protection.requiredApprovingReviewCount!r}",
                )
                return

        if pull_request.reviewDecision == PullRequestReviewDecision.REVIEW_REQUIRED:
            await block_merge(api, pull_request, "missing required reviews")
            return

        if (
            branch_protection.requiresConversationResolution
            and pull_request.reviewThreads.nodes is not None
            and any(pr.isCollapsed is False for pr in pull_request.reviewThreads.nodes)
        ):
            await block_merge(api, pull_request, "unresolved conversations")
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

            for check_run in deduplicate_check_runs(check_runs):
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
                    CheckConclusionState.CANCELLED,
                    CheckConclusionState.SKIPPED,
                    CheckConclusionState.STALE,
                ):
                    failing_contexts.append(check_run.name)
            passing = set(passing_contexts)
            failing = set(failing_contexts)
            # we have failing statuses that are required
            failing_required_status_checks = failing & required
            # GitHub has undocumented logic for travis-ci checks in GitHub
            # branch protection rules. GitHub compresses
            # "continuous-integration/travis-ci/{pr,push}" to
            # "continuous-integration/travis-ci". There is only special handling
            # for these specific checks.
            if "continuous-integration/travis-ci" in required:
                if "continuous-integration/travis-ci/pr" in failing:
                    failing_required_status_checks.add(
                        "continuous-integration/travis-ci/pr"
                    )
                if "continuous-integration/travis-ci/push" in failing:
                    failing_required_status_checks.add(
                        "continuous-integration/travis-ci/push"
                    )
                # either check can satisfy continuous-integration/travis-ci, but
                # if either fails they'll also block the merge.
                if (
                    "continuous-integration/travis-ci/pr" in passing
                    or "continuous-integration/travis-ci/push" in passing
                ):
                    required.remove("continuous-integration/travis-ci")
            if failing_required_status_checks:
                # NOTE(chdsbd): We need to skip this PR because it would block
                # the merge queue. We may be able to bump it to the back of the
                # queue, but it's easier just to remove it all together. There
                # is a similar question for the review counting.
                await block_merge(
                    api,
                    pull_request,
                    f"failing required status checks: {failing_required_status_checks!r}",
                )
                return
            if skippable_contexts:
                if merging:
                    if skippable_check_timeout > 0:
                        await set_status(
                            f"⛴ merging PR (waiting a bit for dont_wait_on_status_checks: {skippable_contexts!r})"
                        )
                        raise RetryForSkippableChecks
                    log.warning(
                        "timeout reached waiting for dont_wait_on_status_checks",
                        skippable_contexts=skippable_contexts,
                    )
                    await set_status(
                        f"⚠️ timeout reached for dont_wait_on_status_checks: {skippable_contexts!r}"
                    )
                await set_status(
                    f"🛑 not waiting for dont_wait_on_status_checks: {skippable_contexts!r}"
                )
                return

        missing_required_status_checks = required - passing
        wait_for_checks = bool(
            branch_protection.requiresStatusChecks and missing_required_status_checks
        )

        if config.merge.update_branch_immediately and need_branch_update:
            await set_status(
                "🔄 updating branch",
                markdown_content="branch updated because `merge.update_branch_immediately = true` is configured.",
            )
            await api.update_branch()
            if merging:
                raise PollForever
            return

        if merging:
            # prioritize branch updates over waiting for status checks to complete
            if config.merge.optimistic_updates:
                if need_branch_update:
                    await set_status("⛴ merging PR (updating branch)")
                    await api.update_branch()
                    raise PollForever
                if wait_for_checks:
                    await set_status(
                        f"⛴ merging PR (waiting for status checks: {missing_required_status_checks!r})"
                    )
                    raise PollForever
            # almost the same as the pervious case, but we prioritize status checks
            # over branch updates.
            else:
                if wait_for_checks:
                    await set_status(
                        f"⛴ merging PR (waiting for status checks: {missing_required_status_checks!r})"
                    )
                    raise PollForever
                if need_branch_update:
                    await set_status("⛴ merging PR (updating branch)")
                    await api.update_branch()
                    raise PollForever

        # if we reach this point and we don't need to wait for checks or update a branch we've failed to calculate why the PR is blocked. This should _not_ happen normally.
        if not (wait_for_checks or need_branch_update):
            await block_merge(
                api, pull_request, "Merging blocked by GitHub requirements"
            )
            log.warning("merge blocked for unknown reason")
            return
    ready_to_merge = not (wait_for_checks or need_branch_update)

    if config.merge.do_not_merge:
        if wait_for_checks:
            await set_status(
                f"⌛️ waiting for required status checks: {missing_required_status_checks!r}"
            )
        elif need_branch_update:
            await set_status(
                "⚠️ need branch update (suggestion: use merge.update_branch_immediately with merge.do_not_merge)",
                markdown_content="""\
When `merge.do_not_merge = true` is configured `merge.update_branch_immediately = true` \
is recommended so Kodiak can automatically update branches.

By default, Kodiak is efficient and only update branches when merging a PR, but \
when `merge.do_not_merge` is enabled, Kodiak never has that opportunity to \
update a branch during merge. `merge.update_branch_immediately = true` will \
trigger Kodiak to update branches whenever a PR is outdated and not failing any \
branch protection requirements.
""",
            )
        else:
            await set_status("✅ okay to merge")
        log.info(
            "eligible to merge, stopping because config.merge.do_not_merge is enabled."
        )
        return

    # okay to merge if we reach this point.

    if (config.merge.prioritize_ready_to_merge and ready_to_merge) or merging:
        merge_args = get_merge_body(config, merge_method, pull_request, commits=commits)
        await set_status("⛴ attempting to merge PR (merging)")
        try:
            # Use the Git Refs API to rebase merge.
            #
            # This preserves the rebased commits and their hashes. Using the
            # GitHub Pull Request API to rebase merge rewrites the rebased
            # commits, so the commit hashes change.
            #
            # For build systems that depend on commit hashes instead of tree
            # hashes, it's desirable to not rewrite commits.
            if merge_args.merge_method is MergeMethod.rebase_fast_forward:
                await api.update_ref(
                    ref=pull_request.baseRefName, sha=pull_request.latest_sha
                )
            else:
                await api.merge(
                    merge_method=merge_args.merge_method,
                    commit_title=merge_args.commit_title,
                    commit_message=merge_args.commit_message,
                )
        # if we encounter an internal server error (status code 500), it is
        # _not_ safe to retry. Instead we mark the pull request as unmergable
        # and require a user to re-enable Kodiak on the pull request.
        except GitHubApiInternalServerError:
            logger.warning(
                "kodiak encountered GitHub API error merging pull request",
                exc_info=True,
            )
            # We add the disable_bot_label to disable Kodiak from taking any
            # action to update, approve, comment, label, or merge.
            disable_bot_label = config.disable_bot_label
            await api.add_label(disable_bot_label)

            await block_merge(
                api, pull_request, "Cannot merge due to GitHub API failure."
            )
            body = messages.format(
                textwrap.dedent(
                    f"""
            This PR could not be merged because the GitHub API returned an internal server error. To enable Kodiak on this pull request please remove the `{disable_bot_label}` label.

            When the GitHub API returns an internal server error (HTTP status code 500), it is not safe for Kodiak to retry merging.

            For more information please see https://kodiakhq.com/docs/troubleshooting#merge-errors
            """
                )
            )
            await api.create_comment(body)
        else:
            await set_status("merge complete 🎉")

    else:
        priority_merge = config.merge.priority_merge_label in pull_request.labels
        position_in_queue = await api.queue_for_merge(first=priority_merge)
        if position_in_queue is None:
            # this case should be rare/impossible.
            log.warning("couldn't find position for enqueued PR")
            return
        ordinal_position = inflection.ordinalize(position_in_queue + 1)
        if not is_active_merge:
            await set_status(f"📦 enqueued for merge (position={ordinal_position})")
        else:
            log.info(
                "not setting status message for enqueued job because is_active_merge=True"
            )
    return
