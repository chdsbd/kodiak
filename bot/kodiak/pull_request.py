from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Type

import structlog
from requests_async import HTTPError
from typing_extensions import Protocol

import kodiak.app_config as conf
from kodiak.errors import (
    ApiCallException,
    GitHubApiInternalServerError,
    PollForever,
    RetryForSkippableChecks,
)
from kodiak.evaluation import mergeable
from kodiak.queries import Client, EventInfoResponse

logger = structlog.get_logger()


RETRY_RATE_SECONDS = 2
POLL_RATE_SECONDS = 3


async def get_pr(
    install: str,
    owner: str,
    repo: str,
    number: int,
    dequeue_callback: Callable[[], Awaitable[None]],
    requeue_callback: Callable[[], Awaitable[None]],
    queue_for_merge_callback: QueueForMergeCallback,
) -> Optional[PRV2]:
    log = logger.bind(install=install, owner=owner, repo=repo, number=number)
    async with Client(installation_id=install, owner=owner, repo=repo) as api_client:
        default_branch_name = await api_client.get_default_branch_name()
        if default_branch_name is None:
            log.info("failed to find default_branch_name")
            return None
        event = await api_client.get_event_info(
            branch_name=default_branch_name, pr_number=number
        )
        if event is None:
            log.info("failed to find event")
            return None
        return PRV2(
            event,
            install=install,
            owner=owner,
            repo=repo,
            number=number,
            dequeue_callback=dequeue_callback,
            requeue_callback=requeue_callback,
            queue_for_merge_callback=queue_for_merge_callback,
        )


@dataclass(frozen=True)
class APICallError:
    api_name: str
    http_status: str
    response_body: str


async def evaluate_pr(
    install: str,
    owner: str,
    repo: str,
    number: int,
    merging: bool,
    dequeue_callback: Callable[[], Awaitable[None]],
    requeue_callback: Callable[[], Awaitable[None]],
    queue_for_merge_callback: QueueForMergeCallback,
    is_active_merging: bool,
) -> None:
    skippable_check_timeout = 4
    api_call_retries_remaining = 5
    api_call_errors = []  # type: List[APICallError]
    log = logger.bind(install=install, owner=owner, repo=repo, number=number)
    while True:
        log.info("get_pr")
        try:
            pr = await asyncio.wait_for(
                get_pr(
                    install=install,
                    owner=owner,
                    repo=repo,
                    number=number,
                    dequeue_callback=dequeue_callback,
                    requeue_callback=requeue_callback,
                    queue_for_merge_callback=queue_for_merge_callback,
                ),
                timeout=30,
            )
            if pr is None:
                log.info("failed to get_pr")
                return
            try:
                await asyncio.wait_for(
                    mergeable(
                        api=pr,
                        subscription=pr.event.subscription,
                        config=pr.event.config,
                        config_str=pr.event.config_str,
                        config_path=pr.event.config_file_expression,
                        app_id=conf.GITHUB_APP_ID,
                        repository=pr.event.repository,
                        pull_request=pr.event.pull_request,
                        branch_protection=pr.event.branch_protection,
                        review_requests=pr.event.review_requests,
                        reviews=pr.event.reviews,
                        contexts=pr.event.status_contexts,
                        check_runs=pr.event.check_runs,
                        commits=pr.event.commits,
                        valid_signature=pr.event.valid_signature,
                        valid_merge_methods=pr.event.valid_merge_methods,
                        merging=merging,
                        is_active_merge=is_active_merging,
                        skippable_check_timeout=skippable_check_timeout,
                        api_call_errors=api_call_errors,
                        api_call_retries_remaining=api_call_retries_remaining,
                    ),
                    timeout=30,
                )
                log.info("evaluate_pr successful")
            except RetryForSkippableChecks:
                if skippable_check_timeout > 0:
                    skippable_check_timeout -= 1
                    log.info("waiting for skippable checks to pass")
                    await asyncio.sleep(RETRY_RATE_SECONDS)
                    continue
            except PollForever:
                log.info("polling")
                await asyncio.sleep(POLL_RATE_SECONDS)
                continue
            except ApiCallException as e:
                # if we have some api exception, it's likely a temporary error that
                # can be resolved by calling GitHub again.
                if api_call_retries_remaining:
                    api_call_errors.append(
                        APICallError(
                            api_name=e.method,
                            http_status=str(e.status_code),
                            response_body=str(e.response),
                        )
                    )
                    api_call_retries_remaining -= 1
                    log.info("problem contacting remote api. retrying")
                    continue
                log.exception("api_call_retries_remaining")
            return
        except asyncio.TimeoutError:
            # On timeout we add the PR to the back of the queue to try again.
            log.exception("mergeable_timeout")
            await requeue_callback()


class QueueForMergeCallback(Protocol):
    async def __call__(self, *, first: bool) -> Optional[int]:
        ...


class PRV2:
    """
    Representation of a PR for Kodiak.

    This class implements the PRAPI protocol found in evaluation.py
    """

    event: EventInfoResponse

    def __init__(
        self,
        event: EventInfoResponse,
        install: str,
        owner: str,
        repo: str,
        number: int,
        dequeue_callback: Callable[[], Awaitable[None]],
        requeue_callback: Callable[[], Awaitable[None]],
        queue_for_merge_callback: QueueForMergeCallback,
        client: Optional[Type[Client]] = None,
    ):
        self.install = install
        self.owner = owner
        self.repo = repo
        self.number = number
        self.event = event
        self.dequeue_callback = dequeue_callback
        self.requeue_callback = requeue_callback
        self.queue_for_merge_callback = queue_for_merge_callback
        self.log = logger.bind(install=install, owner=owner, repo=repo, number=number)
        self.client = client or Client

    async def dequeue(self) -> None:
        self.log.info("dequeue")
        await self.dequeue_callback()

    async def requeue(self) -> None:
        self.log.info("requeue")
        await self.requeue_callback()

    async def set_status(
        self,
        msg: str,
        *,
        latest_commit_sha: str,
        markdown_content: Optional[str] = None,
    ) -> None:
        """
        Display a message to a user through a github check

        `markdown_content` is the message displayed on the detail view for a
        status check. This detail view is accessible via the "Details" link
        alongside the summary/detail content.
        """
        self.log.info("set_status", message=msg, markdown_content=markdown_content)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.create_notification(
                head_sha=self.event.pull_request.latest_sha,
                message=msg,
                summary=markdown_content,
            )
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to create notification", res=res)

    async def pull_requests_for_ref(self, ref: str) -> Optional[int]:
        log = self.log.bind(ref=ref)
        log.info("pull_requests_for_ref", ref=ref)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            prs = await api_client.get_open_pull_requests(base=ref)
            if prs is None:
                # our api request failed.
                log.info("failed to get pull request info for ref")
                return None
            return len(prs)

    async def delete_branch(self, branch_name: str) -> None:
        self.log.info("delete_branch", branch_name=branch_name)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.delete_branch(branch=branch_name)
            try:
                res.raise_for_status()
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 422:
                    self.log.info("branch already deleted, nothing to do", res=res)
                else:
                    self.log.exception("failed to delete branch", res=res)

    async def update_branch(self) -> None:
        self.log.info("update_branch")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.update_branch(pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to update branch", res=res)
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/update_branch",
                    http_status_code=res.status_code,
                    response=res.content,
                )

    async def approve_pull_request(self) -> None:
        self.log.info("approve_pull_request")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.approve_pull_request(pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to approve pull request", res=res)

    async def trigger_test_commit(self) -> None:
        self.log.info("trigger_test_commit")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.get_pull_request(number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception(
                    "failed to get pull request for test commit trigger", res=res
                )

    async def merge(
        self,
        merge_method: str,
        commit_title: Optional[str],
        commit_message: Optional[str],
    ) -> None:
        self.log.info("merge", method=merge_method)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.merge_pull_request(
                number=self.number,
                merge_method=merge_method,
                base=self.event.pull_request.baseRefName,
                branch=self.event.pull_request.headRefName,
                commit_title=commit_title,
                commit_message=commit_message,
            )
            try:
                res.raise_for_status()
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 405:
                    self.log.info(
                        "branch is not mergeable. PR likely already merged.", res=res
                    )
                else:
                    self.log.exception("failed to merge pull request", res=res)
                if e.response is not None and e.response.status_code == 500:
                    raise GitHubApiInternalServerError
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/merge",
                    http_status_code=res.status_code,
                    response=res.content,
                )

    async def queue_for_merge(self, *, first: bool) -> Optional[int]:
        self.log.info("queue_for_merge")
        return await self.queue_for_merge_callback(first=first)

    async def add_label(self, label: str) -> None:
        """
        add label to pull request
        """
        self.log.info("add_label", label=label)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.add_label(label, pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to add label", label=label, res=res)
                raise ApiCallException(
                    method="pull_request/add_label",
                    http_status_code=res.status_code,
                    response=res.content,
                )

    async def remove_label(self, label: str) -> None:
        """
        remove the PR label specified by `label_id` for a given `pr_number`
        """
        self.log.info("remove_label", label=label)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.delete_label(label, pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to delete label", label=label, res=res)
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/delete_label",
                    http_status_code=res.status_code,
                    response=res.content,
                )

    async def create_comment(self, body: str) -> None:
        """
       create a comment on the specified `pr_number` with the given `body` as text.
        """
        self.log.info("create_comment", body=body)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.create_comment(body=body, pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.exception("failed to create comment", res=res)
