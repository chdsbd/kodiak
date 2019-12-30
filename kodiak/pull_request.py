import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Tuple, cast

import structlog
from typing_extensions import Literal

import kodiak.app_config as conf
from kodiak import queries
from kodiak.config import V1
from kodiak.errors import ApiCallException, PollForever, RetryForSkippableChecks
from kodiak.evaluation import mergeable
from kodiak.queries import Client, EventInfoResponse

logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


RETRY_RATE_SECONDS = 2
POLL_RATE_SECONDS = 3


async def get_pr(
    install: str,
    owner: str,
    repo: str,
    number: int,
    dequeue_callback: Callable[[], Awaitable],
) -> PRV2:

    async with Client(installation_id=install, owner=owner, repo=repo) as api_client:
        default_branch_name = await api_client.get_default_branch_name()
        if default_branch_name is None:
            raise RuntimeError
        event = await api_client.get_event_info(
            config_file_expression=create_git_revision_expression(
                branch=default_branch_name, file_path=CONFIG_FILE_PATH
            ),
            pr_number=number,
        )
        if event is None:
            raise RuntimeError
        return PRV2(
            event,
            install=install,
            owner=owner,
            repo=repo,
            number=number,
            dequeue_callback=dequeue_callback,
        )


async def evaluate_pr(
    install: str,
    owner: str,
    repo: str,
    number: int,
    merging: bool,
    dequeue_callback: Callable[[], Awaitable],
    is_active_merging: bool,
) -> None:
    skippable_check_timeout = 4
    api_call_retry_timeout = 5
    log = logger.bind(install=install, owner_repo=f"{owner}/{repo}", number=number)
    while True:
        pr = await get_pr(
            install=install,
            owner=owner,
            repo=repo,
            number=number,
            dequeue_callback=dequeue_callback,
        )
        try:
            mergeable(
                api=pr,
                config=pr.event.config,
                config_str=pr.event.config_str,
                config_path=pr.event.config_file_expression,
                app_id=conf.GITHUB_APP_ID,
                pull_request=pr.event.pull_request,
                branch_protection=pr.event.branch_protection,
                review_requests=pr.event.review_requests,
                reviews=pr.event.reviews,
                contexts=pr.event.status_contexts,
                check_runs=pr.event.check_runs,
                valid_signature=pr.event.valid_signature,
                valid_merge_methods=pr.event.valid_merge_methods,
                merging=merging,
                is_active_merge=is_active_merging,
            )
        except RetryForSkippableChecks:
            if skippable_check_timeout:
                skippable_check_timeout -= 1
                log.info("waiting for skippable checks to pass")
                await asyncio.sleep(RETRY_RATE_SECONDS)
                continue
        except PollForever:
            log.info("polling")
            await asyncio.sleep(POLL_RATE_SECONDS)
            continue
        except ApiCallException:
            # if we have some api exception, it's likely a temporary error that
            # can be resolved by calling GitHub again.
            if api_call_retry_timeout:
                api_call_retry_timeout -= 1
                log.exception("problem contacting remote api. retrying")
                continue
            log.exception("api_call_retry_timeout")
        break


class PRV2:
    event: EventInfoResponse

    def __init__(
        self,
        event: EventInfoResponse,
        install: str,
        owner: str,
        repo: str,
        number: int,
        dequeue_callback: Callable[[], Awaitable],
    ):
        self.install = install
        self.owner = owner
        self.repo = repo
        self.number = number
        self.event = event
        self.dequeue_callback = dequeue_callback

    async def dequeue(self) -> None:
        await self.dequeue_callback()

    async def set_status(
        self,
        msg: str,
        *,
        latest_commit_sha: str,
        kind: Optional[Literal["cfg_err", "blocked", "loading", "updating"]] = None,
        markdown_content: Optional[str] = None,
    ) -> None:
        """
        Display a message to a user through a github check

        `markdown_content` is the message displayed on the detail view for a
        status check. This detail view is accessible via the "Details" link
        alongside the summary/detail content.
        """
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            await api_client.create_notification(
                head_sha=self.event.pull_request.latest_sha,
                message=msg,
                summary=markdown_content,
            )

    async def delete_branch(self, branch_name: str) -> None:
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            await api_client.delete_branch(branch=branch_name)

    async def update_branch(self) -> None:
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            await api_client.update_branch(pull_number=self.number)

    async def trigger_test_commit(self) -> None:
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            await api_client.get_pull_request(number=self.number)

    async def merge(
        self,
        merge_method: str,
        commit_title: Optional[str],
        commit_message: Optional[str],
    ) -> None:
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.merge_pull_request(
                number=self.number,
                merge_method=merge_method,
                commit_title=commit_title,
                commit_message=commit_message,
            )
            if not res.ok:
                raise ApiCallException

    async def remove_label(self, label: str) -> None:
        """
        remove the PR label specified by `label_id` for a given `pr_number`
        """
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.delete_label(label, pull_number=self.number)
            if not res.ok:
                raise ApiCallException

    async def create_comment(self, body: str) -> None:
        """
       create a comment on the speicifed `pr_number` with the given `body` as text.
        """
        async with Client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            await api_client.create_comment(body=body, pull_number=self.number)
