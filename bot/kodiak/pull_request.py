from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional, Type

import structlog
from typing_extensions import Protocol

import kodiak.app_config as conf
from kodiak.errors import (
    ApiCallException,
    GitHubApiInternalServerError,
    PollForever,
    RetryForSkippableChecks,
)
from kodiak.evaluation import mergeable
from kodiak.http import (
    HTTPStatusError as HTTPError,
    Response,
)
from kodiak.queries import Client, EventInfoResponse

logger = structlog.get_logger()


RETRY_RATE_SECONDS = 2
POLL_RATE_SECONDS = 3
MERGE_POLL_RATE_SECONDS = 1
# GitHub merges in the background, which can take a couple minutes for a stack
# of pull requests. We stop polling before kodiak's own evaluation timeout so we
# retry the evaluation instead of being killed mid merge.
MERGE_POLL_TIMEOUT_SECONDS = 30

# status codes of merge-async responses that carry a merge result.
MERGE_STATUS_CODES = frozenset(
    {
        200,  # already merged, or a result for a merge we started
        202,  # merge started
        400,  # pull request cannot be merged
        409,  # a merge is already in flight for this pull request
    }
)


class MergeStatus:
    """
    https://github.github.com/gh-stack/reference/merge-api/
    """

    pending = "pending"
    merged = "merged"
    enqueued = "enqueued"
    failed = "failed"


@dataclass(frozen=True)
class MergeResult:
    status: str
    details: Mapping[str, Any]


def parse_merge_result(res: Response) -> Optional[MergeResult]:
    try:
        body = res.json()
        status = body["status"]
        details = body.get("details") or {}
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(status, str) or not isinstance(details, dict):
        return None
    return MergeResult(status=status, details=details)


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
        event = await api_client.get_event_info(pr_number=number)
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
    log: structlog.BoundLogger,
) -> None:
    skippable_check_timeout = 4
    api_call_retries_remaining = 5
    api_call_errors = []  # type: list[APICallError]
    log = log.bind(owner=owner, repo=repo, number=number, merging=merging)
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
                timeout=60,
            )
            try:
                if pr is None:
                    log.info("failed to get_pr")
                    if merging:
                        raise ApiCallException(
                            method="kodiak/get_pr",
                            http_status_code=0,
                            response=b"",
                        )
                    return
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
                        ruleset_rules=pr.event.ruleset_rules,
                        review_requests=pr.event.review_requests,
                        bot_reviews=pr.event.bot_reviews,
                        contexts=pr.event.status_contexts,
                        check_runs=pr.event.check_runs,
                        commits=pr.event.commits,
                        valid_merge_methods=pr.event.valid_merge_methods,
                        merging=merging,
                        is_active_merge=is_active_merging,
                        skippable_check_timeout=skippable_check_timeout,
                        api_call_errors=api_call_errors,
                        api_call_retries_remaining=api_call_retries_remaining,
                    ),
                    timeout=60,
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
                log.warning("api_call_retries_remaining", exc_info=True)
            return
        except asyncio.TimeoutError:
            # On timeout we add the PR to the back of the queue to try again.
            log.warning("mergeable_timeout", exc_info=True)
            await requeue_callback()


class QueueForMergeCallback(Protocol):
    async def __call__(self, *, first: bool) -> Optional[int]: ...


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
        self, msg: str, *, markdown_content: Optional[str] = None
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
                self.log.warning(
                    "failed to create notification", res=res, exc_info=True
                )

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
                    self.log.warning("failed to delete branch", res=res, exc_info=True)

    async def update_branch(self) -> None:
        self.log.info("update_branch")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.update_branch(pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError as e:
                self.log.warning("failed to update branch", res=res, exc_info=True)
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/update_branch",
                    http_status_code=res.status_code,
                    response=res.content,
                ) from e

    async def approve_pull_request(self) -> None:
        self.log.info("approve_pull_request")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.approve_pull_request(pull_number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.warning(
                    "failed to approve pull request", res=res, exc_info=True
                )

    async def trigger_test_commit(self) -> None:
        self.log.info("trigger_test_commit")
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.get_pull_request(number=self.number)
            try:
                res.raise_for_status()
            except HTTPError:
                self.log.warning(
                    "failed to get pull request for test commit trigger",
                    res=res,
                    exc_info=True,
                )

    def _parse_merge_response(self, res: Response, *, method: str) -> MergeResult:
        """
        Read the result of a merge-async response, raising for anything that
        isn't a valid result.
        """
        if res.status_code in MERGE_STATUS_CODES:
            result = parse_merge_result(res)
            if result is not None:
                return result
        try:
            res.raise_for_status()
        except HTTPError as e:
            self.log.warning("failed to merge pull request", res=res, exc_info=True)
            if e.response is not None and e.response.status_code == 500:
                raise GitHubApiInternalServerError from e
            # we raise an exception to retry this request.
            raise ApiCallException(
                method=method,
                http_status_code=res.status_code,
                response=res.content,
            ) from e
        self.log.warning("could not parse merge result", res=res)
        raise ApiCallException(
            method=method,
            http_status_code=res.status_code,
            response=res.content,
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
                commit_title=commit_title,
                commit_message=commit_message,
            )
            result = self._parse_merge_response(res, method="pull_request/merge")

            # merging runs in the background so we poll until we have a result.
            deadline = time.monotonic() + MERGE_POLL_TIMEOUT_SECONDS
            while result.status == MergeStatus.pending:
                uuid = result.details.get("uuid")
                if not isinstance(uuid, str):
                    self.log.warning("missing uuid for pending merge", res=res)
                    raise ApiCallException(
                        method="pull_request/merge",
                        http_status_code=res.status_code,
                        response=res.content,
                    )
                if time.monotonic() > deadline:
                    # we raise an exception to retry this request. Starting the
                    # merge again returns the uuid of the in-flight merge, so we
                    # resume polling instead of merging twice.
                    self.log.info("timeout waiting for merge to finish", res=res)
                    raise ApiCallException(
                        method="pull_request/merge",
                        http_status_code=res.status_code,
                        response=res.content,
                    )
                await asyncio.sleep(MERGE_POLL_RATE_SECONDS)
                res = await api_client.get_merge_pull_request_result(
                    number=self.number, uuid=uuid
                )
                result = self._parse_merge_response(
                    res, method="pull_request/merge_result"
                )

            if result.status == MergeStatus.merged:
                return
            if result.status == MergeStatus.enqueued:
                self.log.info("pull request added to merge queue", res=res)
                return
            # a merge can fail for a merge conflict, an unmet branch protection
            # rule, a closed pull request, etc. Nothing was merged.
            self.log.warning(
                "failed to merge pull request",
                res=res,
                merge_status=result.status,
                message=result.details.get("message"),
            )
            # we raise an exception to retry this request.
            raise ApiCallException(
                method="pull_request/merge",
                http_status_code=res.status_code,
                response=res.content,
            )

    async def update_ref(self, ref: str, sha: str) -> None:
        self.log.info("update_ref", ref=ref, sha=sha)
        async with self.client(
            installation_id=self.install, owner=self.owner, repo=self.repo
        ) as api_client:
            res = await api_client.update_ref(ref=ref, sha=sha)
            try:
                res.raise_for_status()
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 422:
                    self.log.info("fast forward update not possible.", res=res)
                else:
                    self.log.warning("failed to update ref", res=res, exc_info=True)
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/update_ref",
                    http_status_code=res.status_code,
                    response=res.content,
                ) from e

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
            except HTTPError as exc:
                self.log.warning(
                    "failed to add label", label=label, res=res, exc_info=True
                )
                raise ApiCallException(
                    method="pull_request/add_label",
                    http_status_code=res.status_code,
                    response=res.content,
                ) from exc

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
            except HTTPError as exc:
                self.log.warning(
                    "failed to delete label", label=label, res=res, exc_info=True
                )
                # we raise an exception to retry this request.
                raise ApiCallException(
                    method="pull_request/delete_label",
                    http_status_code=res.status_code,
                    response=res.content,
                ) from exc

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
                self.log.warning("failed to create comment", res=res, exc_info=True)
