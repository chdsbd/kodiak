import textwrap
import typing
from dataclasses import dataclass
from enum import Enum, auto

import structlog

import kodiak.app_config as conf
from kodiak import queries
from kodiak.config import V1, BodyText, MergeBodyStyle, MergeTitleStyle
from kodiak.errors import (
    BranchMerged,
    MergeConflict,
    MissingAppID,
    MissingGithubMergeabilityState,
    NeedsBranchUpdate,
    NotQueueable,
    WaitingForChecks,
)
from kodiak.evaluation import mergeable
from kodiak.queries import EventInfoResponse, PullRequest, get_headers

logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"


class MergeabilityResponse(Enum):
    OK = auto()
    NEEDS_UPDATE = auto()
    NEED_REFRESH = auto()
    NOT_MERGEABLE = auto()
    WAIT = auto()


def strip_html_comments_from_markdown(message: str) -> str:
    """
    1. parse string into a markdown AST
    2. find the HTML nodes
    3. parse HTML nodes into HTML
    4. find comments in HTML
    5. slice out comments from original message
    """
    return message


def get_body_content(
    body_type: BodyText, strip_html_comments: bool, pull_request: PullRequest
) -> str:
    if body_type == BodyText.markdown:
        body = pull_request.body
        if strip_html_comments:
            body = strip_html_comments_from_markdown(body)
        return body
    if body_type == BodyText.plain_text:
        return pull_request.bodyText
    if body_type == BodyText.html:
        return pull_request.bodyHTML
    raise Exception(f"Unknown body_type: {body_type}")


def get_merge_body(config: V1, pull_request: PullRequest) -> dict:
    merge_body: dict = {"merge_method": config.merge.method.value}
    if config.merge.message.body == MergeBodyStyle.pull_request_body:
        body = get_body_content(config.merge.message.body_type, pull_request)
        merge_body.update(dict(commit_message=body))
    if config.merge.message.title == MergeTitleStyle.pull_request_title:
        merge_body.update(dict(commit_title=pull_request.title))
    if config.merge.message.include_pr_number and merge_body.get("commit_title"):
        merge_body["commit_title"] += f" (#{pull_request.number})"
    return merge_body


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


@dataclass(init=False, repr=False, eq=False)
class PR:
    number: int
    owner: str
    repo: str
    installation_id: str
    log: structlog.BoundLogger
    event: typing.Optional[EventInfoResponse]
    client: queries.Client

    def __eq__(self, b: object) -> bool:
        if not isinstance(b, PR):
            raise NotImplementedError
        return (
            self.number == b.number
            and self.owner == b.owner
            and self.repo == b.repo
            and self.installation_id == b.installation_id
        )

    def __init__(
        self,
        number: int,
        owner: str,
        repo: str,
        installation_id: str,
        client: queries.Client,
    ):
        self.number = number
        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        self.client = client
        self.event = None
        self.log = logger.bind(repo=f"{owner}/{repo}#{number}")

    def __repr__(self) -> str:
        return f"<PR path='{self.owner}/{self.repo}#{self.number}'>"

    async def get_event(self) -> typing.Optional[EventInfoResponse]:
        default_branch_name = await self.client.get_default_branch_name()
        if default_branch_name is None:
            return None
        return await self.client.get_event_info(
            config_file_expression=create_git_revision_expression(
                branch=default_branch_name, file_path=CONFIG_FILE_PATH
            ),
            pr_number=self.number,
        )

    async def set_status(
        self, summary: str, detail: typing.Optional[str] = None
    ) -> None:
        """
        Display a message to a user through a github check
        """
        if detail is not None:
            message = f"{summary} ({detail})"
        else:
            message = summary
        if self.event is None:
            self.event = await self.get_event()
        assert self.event is not None
        await self.client.create_notification(
            head_sha=self.event.pull_request.latest_sha, message=message, summary=None
        )

    # TODO(chdsbd): Move set_status updates out of this method
    async def mergeability(
        self, merging: bool = False
    ) -> typing.Tuple[MergeabilityResponse, typing.Optional[EventInfoResponse]]:
        self.log.info("get_event")
        self.event = await self.get_event()
        if self.event is None:
            self.log.info("no event")
            return MergeabilityResponse.NOT_MERGEABLE, None
        if not self.event.head_exists:
            self.log.info("branch deleted")
            return MergeabilityResponse.NOT_MERGEABLE, None
        try:
            self.log.info("check mergeable")
            mergeable(
                config=self.event.config,
                app_id=conf.GITHUB_APP_ID,
                pull_request=self.event.pull_request,
                branch_protection=self.event.branch_protection,
                review_requests_count=self.event.review_requests_count,
                reviews=self.event.reviews,
                contexts=self.event.status_contexts,
                check_runs=self.event.check_runs,
                valid_signature=self.event.valid_signature,
                valid_merge_methods=self.event.valid_merge_methods,
            )
            self.log.info("okay")
            return MergeabilityResponse.OK, self.event
        except (NotQueueable, MergeConflict, BranchMerged) as e:
            if (
                isinstance(e, MergeConflict)
                and self.event.config.merge.notify_on_conflict
            ):
                await self.notify_pr_creator()

            if (
                isinstance(e, BranchMerged)
                and self.event.config.merge.delete_branch_on_merge
            ):
                await self.client.delete_branch(
                    branch=self.event.pull_request.headRefName
                )

            await self.set_status(summary="🛑 cannot merge", detail=str(e))
            return MergeabilityResponse.NOT_MERGEABLE, self.event
        except MissingAppID:
            return MergeabilityResponse.NOT_MERGEABLE, self.event
        except MissingGithubMergeabilityState:
            self.log.info("missing mergeability state, need refresh")
            return MergeabilityResponse.NEED_REFRESH, self.event
        except WaitingForChecks:
            if merging:
                await self.set_status(
                    summary="⛴ attempting to merge PR", detail="waiting for checks"
                )
            return MergeabilityResponse.WAIT, self.event
        except NeedsBranchUpdate:
            if merging:
                await self.set_status(
                    summary="⛴ attempting to merge PR", detail="updating branch"
                )
            return MergeabilityResponse.NEEDS_UPDATE, self.event

    async def update(self) -> None:
        self.log.info("update")
        event = await self.get_event()
        if event is None:
            self.log.warning("problem")
            return
        await self.client.merge_branch(
            head=event.pull_request.baseRefName, base=event.pull_request.headRefName
        )

    async def trigger_mergeability_check(self) -> None:
        await self.client.get_pull_request(number=self.number)

    async def merge(self, event: EventInfoResponse) -> bool:
        res = await self.client.merge_pull_request(
            number=self.number, body=get_merge_body(event.config, event.pull_request)
        )
        return not res.status_code > 300

    async def delete_label(self, label: str) -> bool:
        """
        remove the PR label specified by `label_id` for a given `pr_number`
        """
        self.log.info("deleting label", label=label)
        headers = await get_headers(installation_id=self.installation_id)
        res = await self.client.session.delete(
            f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}/labels/{label}",
            headers=headers,
        )
        return typing.cast(bool, res.status_code != 204)

    async def create_comment(self, body: str) -> bool:
        """
        create a comment on the speicifed `pr_number` with the given `body` as text.
        """
        self.log.info("creating comment", body=body)
        headers = await get_headers(installation_id=self.installation_id)
        res = await self.client.session.post(
            f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{self.number}/comments",
            json=dict(body=body),
            headers=headers,
        )
        return typing.cast(bool, res.status_code != 200)

    async def notify_pr_creator(self) -> bool:
        """
        comment on PR with an `@$PR_CREATOR_NAME` and remove `automerge` label.

        Since we don't have atomicity we chose to remove the label first
        instead of creating the comment first as we would rather have no
        comment instead of multiple comments on each consecutive PR push.
        """

        event = self.event
        if not event:
            return False
        label = event.config.merge.automerge_label
        if not await self.delete_label(label=label):
            return False

        # TODO(sbdchd): add mentioning of PR author in comment.
        body = textwrap.dedent(
            """
        This PR currently has a merge conflict. Please resolve this and then re-add the `automerge` label.
        """
        )
        return await self.create_comment(body)
