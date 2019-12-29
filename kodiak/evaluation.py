import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, MutableMapping, Optional, Set, Tuple, Union

import pydantic
import structlog
import toml
from markdown_html_finder import find_html_positions
from typing_extensions import Literal, Protocol

from kodiak import config
from kodiak.config import V1, BodyText, MergeBodyStyle, MergeMethod, MergeTitleStyle
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


class CommentHTMLParser(HTMLParser):
    # define this attribute to make mypy accept `self.offset`
    offset: int

    def __init__(self) -> None:
        self.comments: List[Tuple[int, int]] = []
        super().__init__()

    def handle_comment(self, tag: str) -> None:
        start_token_len = len("<!--")
        end_token_len = len("-->")
        tag_len = len(tag)
        end = start_token_len + tag_len + end_token_len
        self.comments.append((self.offset, end + self.offset))

    def reset(self) -> None:
        self.comments = []
        super().reset()


html_parser = CommentHTMLParser()


def strip_html_comments_from_markdown(raw_message: str) -> str:
    """
    1. parse string into a markdown AST
    2. find the HTML nodes
    3. parse HTML nodes into HTML
    4. find comments in HTML
    5. slice out comments from original message
    """
    # NOTE(chdsbd): Remove carriage returns so find_html_positions can process
    # html correctly. pulldown-cmark doesn't handle carriage returns well.
    # remark-parse also doesn't handle carriage returns:
    # https://github.com/remarkjs/remark/issues/195#issuecomment-230760892
    message = raw_message.replace("\r", "")
    html_node_positions = find_html_positions(message)
    comment_locations = []
    for html_start, html_end in html_node_positions:
        html_text = message[html_start:html_end]
        html_parser.feed(html_text)
        for comment_start, comment_end in html_parser.comments:
            comment_locations.append(
                (html_start + comment_start, html_start + comment_end)
            )
        html_parser.reset()

    new_message = message
    for comment_start, comment_end in reversed(comment_locations):
        new_message = new_message[:comment_start] + new_message[comment_end:]
    return new_message


def get_body_content(
    body_type: BodyText, strip_html_comments: bool, pull_request: PullRequest
) -> str:
    if body_type == BodyText.markdown:
        body = pull_request.body
        if strip_html_comments:
            return strip_html_comments_from_markdown(body)
        return body
    if body_type == BodyText.plain_text:
        return pull_request.bodyText
    if body_type == BodyText.html:
        return pull_request.bodyHTML
    raise Exception(f"Unknown body_type: {body_type}")


EMPTY_STRING = ""


@dataclass
class MergeBody:
    merge_method: str
    commit_title: Optional[str] = None
    commit_message: Optional[str] = None


def get_merge_body(config: V1, pull_request: PullRequest) -> MergeBody:
    merge_body = MergeBody(merge_method=config.merge.method.value)
    if config.merge.message.body == MergeBodyStyle.pull_request_body:
        body = get_body_content(
            config.merge.message.body_type,
            config.merge.message.strip_html_comments,
            pull_request,
        )
        merge_body.commit_message = body
    if config.merge.message.body == MergeBodyStyle.empty:
        merge_body.commit_message = EMPTY_STRING
    if config.merge.message.title == MergeTitleStyle.pull_request_title:
        merge_body.commit_title = pull_request.title
    if config.merge.message.include_pr_number and merge_body.commit_title is not None:
        merge_body.commit_title += f" (#{pull_request.number})"
    return merge_body


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

class PRAPI(Protocol):
    async def dequeue(self) -> None:
        ...

    async def set_status(
        self,
        msg: str,
        *,
        latest_commit_sha: str,
        kind: Optional[Literal["cfg_err", "blocked", "loading", "updating"]] = None,
        markdown_content: Optional[str] = None,
    ) -> None:
        ...

    async def delete_branch(self, branch_name: str) -> None:
        ...

    async def remove_label(self, label: str) -> None:
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

    async def update_branch(self) -> None:
        ...


async def cfg_err(api: PRAPI, pull_request: PullRequest, msg: str) -> None:
    await api.dequeue()
    await api.set_status(msg, kind="cfg_err", latest_commit_sha=pull_request.latest_sha)


async def block_merge(api: PRAPI, pull_request: PullRequest, msg: str) -> None:
    await api.dequeue()
    await api.set_status(msg, kind="blocked", latest_commit_sha=pull_request.latest_sha)


async def update_branch(api: PRAPI, pull_request: PullRequest) -> None:
    await api.update_branch()
    await api.set_status(
        "updating branch", kind="updating", latest_commit_sha=pull_request.latest_sha
    )


async def mergeable(
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

    async def set_status(
        msg: str,
        kind: Optional[Literal["cfg_err", "blocked", "loading", "updating"]] = None,
    ) -> None:
        await api.set_status(msg, latest_commit_sha=pull_request.latest_sha, kind=kind)

    if not isinstance(config, V1):
        log.warning("problem fetching config")
        return

    # if we have an app_id in the config then we only want to work on this repo
    # if our app_id from the environment matches the configuration.
    if config.app_id is not None and config.app_id != app_id:
        log.info("missing required app_id")
        await api.dequeue()
        return

    if branch_protection is None:
        cfg_err(
            api,
            pull_request,
            f"missing branch protection for baseRef: {pull_request.baseRefName!r}",
        )
        return
    if branch_protection.requiresCommitSignatures:
        cfg_err(
            api,
            pull_request,
            '"Require signed commits" branch protection is not supported. See Kodiak README for more info.',
        )
        return

    if (
        config.merge.require_automerge_label
        and config.merge.automerge_label not in pull_request.labels
    ):
        await block_merge(
            api,
            pull_request,
            f"missing automerge_label: {config.merge.automerge_label!r}",
        )
        return
    blacklist_labels = set(config.merge.blacklist_labels) & set(pull_request.labels)
    if blacklist_labels:
        await block_merge(
            api, pull_request, f"has blacklist_labels: {blacklist_labels!r}"
        )
        return

    if (
        config.merge.blacklist_title_regex
        and re.search(config.merge.blacklist_title_regex, pull_request.title)
        is not None
    ):
        await block_merge(
            api,
            pull_request,
            f"title matches blacklist_title_regex: {config.merge.blacklist_title_regex!r}",
        )
        return

    if pull_request.mergeStateStatus == MergeStateStatus.DRAFT:
        await block_merge(api, pull_request, "pull request is in draft state")
        return

    if config.merge.method not in valid_merge_methods:
        valid_merge_methods_str = [method.value for method in valid_merge_methods]
        cfg_err(
            api,
            pull_request,
            f"configured merge.method {config.merge.method.value!r} is invalid. Valid methods for repo are {valid_merge_methods_str!r}",
        )
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
        if config.merge.delete_branch_on_merge:
            await api.delete_branch(branch_name=pull_request.headRefName)
        return

    if pull_request.state == PullRequestState.CLOSED:
        await api.dequeue()
        return
    if (
        pull_request.mergeStateStatus == MergeStateStatus.DIRTY
        or pull_request.mergeable == MergeableState.CONFLICTING
    ):
        await block_merge(api, pull_request, "merge conflict")
        # remove label if configured and send message
        if config.merge.notify_on_conflict and not config.merge.require_automerge_label:
            automerge_label = config.merge.automerge_label
            await api.remove_label(automerge_label)
            body = textwrap.dedent(
                f"""
            This PR currently has a merge conflict. Please resolve this and then re-add the `{automerge_label}` label.
            """
            )
            await api.create_comment(body)
        return

    if pull_request.mergeStateStatus == MergeStateStatus.UNSTABLE:
        # TODO: This status means that the pr is mergeable but has failing
        # status checks. we may want to handle this via config
        pass

    if pull_request.mergeable == MergeableState.UNKNOWN:
        # we need to trigger a test commit to fix this. We do that by calling
        # GET on the pull request endpoint.
        await api.trigger_test_commit()
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

        if branch_protection.requiresCommitSignatures and not valid_signature:
            await block_merge(api, pull_request, "missing required signature")
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
                await block_merge(
                    api,
                    pull_request,
                    f"failing required status checks: {failing_required_status_checks!r}",
                )
                return
            if skippable_contexts:
                # TODO: How do we wait for skippable checks when merging but not when updating?
                if merging:
                    # TODO: retry for a couple times unless we get something useful
                    raise RetryForSkippableChecks
                await set_status(
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
                await update_branch(api, pull_request)
                return
            if wait_for_checks:
                if merging:
                    # TODO: poll
                    await set_status(
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
                    await set_status(
                        "waiting for required status checks: {missing_required_status_checks!r}",
                        kind="loading",
                    )
                    return
                return
            if need_branch_update:
                await update_branch(api, pull_request)
                return

        await block_merge(api, pull_request, "Merging blocked by GitHub requirements")
        return

    # okay to merge
    merge_args = get_merge_body(config, pull_request)
    await api.merge(
        merge_method=merge_args.merge_method,
        commit_title=merge_args.commit_title,
        commit_message=merge_args.commit_message,
    )
    return
