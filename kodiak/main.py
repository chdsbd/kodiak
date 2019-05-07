from __future__ import annotations
import typing
import asyncio
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum, auto

import toml
from fastapi import FastAPI
import structlog

import kodiak
from kodiak.github import Webhook, events
from kodiak.queries import Client, EventInfoResponse, PullRequest, RepoInfo
from kodiak.evaluation import (
    evaluate_mergability,
    NotMergable,
    NeedsUpdate,
    CheckMergability,
)

app = FastAPI()

webhook = Webhook(app)
logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"

processing_queue: "asyncio.Queue[Event]" = asyncio.Queue()


def create_git_revision_expression(branch: str, file_path: str) -> str:
    return f"{branch}:{file_path}"


@dataclass
class Event:
    repo_owner: str
    repo_name: str
    source_event: events.GithubEvent
    pull_request_number: int
    installation_id: str


@app.get("/")
async def root():
    return "OK"


@webhook()
async def pr_event(pr: events.PullRequestEvent):
    assert pr.installation is not None
    processing_queue.put_nowait(
        Event(
            repo_owner=pr.repository.owner.login,
            repo_name=pr.repository.name,
            pull_request_number=pr.number,
            source_event=pr,
            installation_id=str(pr.installation.id),
        )
    )


@webhook()
async def check_run(check_run_event: events.CheckRunEvent):
    assert check_run_event.installation
    owner = check_run_event.repository.owner.login
    repo = check_run_event.repository.name
    installation_id = check_run_event.installation.id
    for pr in check_run_event.check_run.pull_requests:
        processing_queue.put_nowait(
            Event(
                repo_owner=owner,
                repo_name=repo,
                pull_request_number=pr.number,
                source_event=check_run_event,
                installation_id=str(installation_id),
            )
        )


@webhook()
async def status_event(status_event: events.StatusEvent):
    assert status_event.installation
    raise NotImplementedError
    # TODO: Get PRs for sha and do something like we do with check_run


@webhook()
async def pr_review(review: events.PullRequestReviewEvent):
    assert review.installation
    raise NotImplementedError


@dataclass
class RepoQueue:
    lock: asyncio.Lock = asyncio.Lock()
    queue: typing.Deque[PR] = deque()

    async def enqueue(self, pr: PR) -> None:
        async with self.lock:
            if pr not in self.queue:
                self.queue.append(pr)

    async def dequeue(self, pr: PR) -> None:
        async with self.lock:
            try:
                self.queue.remove(pr)
            except ValueError:
                # pr is not in queue
                pass


@dataclass
class PREventData:
    pull_request: PullRequest
    config: kodiak.config.V1
    repo_info: RepoInfo


class MergeabilityResponse(Enum):
    OK = auto()
    NEEDS_UPDATE = auto()
    NOT_MERGABLE = auto()
    NEED_REFRESH = auto()
    INTERNAL_PROBLEM = auto()


class MergeResults(Enum):
    OK = auto()
    CANNOT_MERGE = auto()
    API_FAILURE = auto()


@dataclass
class PR:
    number: int
    owner: str
    repo: str
    installation_id: str

    async def get_event(self) -> typing.Optional[PREventData]:
        log = logger.bind(
            owner=self.owner,
            repo=self.repo,
            number=self.number,
            installation_id=self.installation_id,
        )
        async with Client() as client:
            default_branch_name = await client.get_default_branch_name(
                owner=self.owner, repo=self.repo, installation_id=self.installation_id
            )
            event_info = await client.get_event_info(
                owner=self.owner,
                repo=self.repo,
                config_file_expression=create_git_revision_expression(
                    branch=default_branch_name, file_path=CONFIG_FILE_PATH
                ),
                pr_number=self.number,
                installation_id=self.installation_id,
            )

            if event_info.config_file is None:
                log.warning("No configuration file found for repo.")
                return None
            if event_info.pull_request is None:
                log.warning("Could not find pull request")
                return None
            if event_info.repo is None:
                log.warning("Could not find repository")
                return None
            try:
                config = kodiak.config.V1.parse_toml(event_info.config_file)
            except (ValueError, toml.TomlDecodeError):
                log.warning(
                    "Failure to parse toml configuration file",
                    config_path=CONFIG_FILE_PATH,
                )
                return None
            return PREventData(
                pull_request=event_info.pull_request,
                config=config,
                repo_info=event_info.repo,
            )

    async def mergability(self) -> MergeabilityResponse:
        log = logger.bind(owner=self.owner, repo=self.repo)
        event = await self.get_event()
        if event is None:
            return MergeabilityResponse.INTERNAL_PROBLEM
        try:
            evaluate_mergability(config=event.config, pull_request=event.pull_request)
            return MergeabilityResponse.OK
        except NotMergable as e:
            log.info("not mergable", reasons=e.reasons)
            return MergeabilityResponse.NOT_MERGABLE
        except NeedsUpdate:
            log.info("needs update")
            return MergeabilityResponse.NEEDS_UPDATE
        except CheckMergability:
            return MergeabilityResponse.NEED_REFRESH

    async def update(self) -> None:
        async with Client() as client:
            event = await self.get_event()
            if event is None:
                logger.warning("problem")
                return
            token = await client.get_token_for_install(
                installation_id=self.installation_id
            )
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )
            res = await client.session.post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/merges",
                json=dict(
                    head=event.pull_request.baseRefName,
                    base=event.pull_request.headRefName,
                ),
                headers=headers,
            )

    async def merge(self) -> MergeResults:
        m_res = await self.mergability()
        log = logger.bind(merge_response=m_res)
        if m_res == MergeabilityResponse.NEEDS_UPDATE:
            await self.update()
        elif m_res == MergeabilityResponse.OK:
            pass
        elif m_res == MergeabilityResponse.NEED_REFRESH:
            pass
        else:
            log.warning("Couldn't merge PR")
            return MergeResults.CANNOT_MERGE
        async with Client() as client:
            token = await client.get_token_for_install(
                installation_id=self.installation_id
            )
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.number}/merge"
            res = await client.session.put(
                url, headers=headers, json={"merge_method": "squash"}
            )
            log.info("merge attemp", res=res, res_json=res.json())
            if res.status_code < 300:
                return MergeResults.OK
            return MergeResults.API_FAILURE


class Retry:
    pass


@dataclass
class RepoWorker:
    q: RepoQueue
    task: asyncio.Task

    async def ingest(self, pr: PR) -> typing.Optional[Retry]:
        log = logger.bind(pr=pr)
        # IF PR needs an update or can be merged, add it to queue
        mergability = await pr.mergability()
        if mergability in (MergeabilityResponse.OK, MergeabilityResponse.NEEDS_UPDATE):
            log.info("queuing", mergability=mergability)
            await self.q.enqueue(pr)
        elif mergability == MergeabilityResponse.NEED_REFRESH:
            log.info("Need to trigger update")
            async with Client() as client:
                token = await client.get_token_for_install(
                    installation_id=pr.installation_id
                )
                headers = dict(
                    Authorization=f"token {token}",
                    Accept="application/vnd.github.machine-man-preview+json",
                )
                url = f"https://api.github.com/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"
                res = await client.session.get(url, headers=headers)
            return Retry()

        else:
            log.info("cannot merge", mergability=mergability)
        return None


REPO_QUEUES: typing.MutableMapping[str, RepoWorker] = dict()


async def work_repo_queue(q: RepoQueue) -> typing.NoReturn:
    while True:
        try:
            logger.info("processing work queue", queue=q.queue)
            async with q.lock:
                try:
                    # TODO: Use asyncio.queue so we can await
                    first = q.queue[0]
                    res = await first.merge()
                    if res == MergeResults.OK:
                        logger.info("merged")
                        q.queue.popleft()
                    elif res == MergeResults.CANNOT_MERGE:
                        q.queue.popleft()
                        logger.info("Cannot merge")
                    else:
                        logger.warning("problem merging", pr=first)
                except IndexError:
                    pass
            # TODO: Use asyncio.queue so we can await instead of busy waiting
            await asyncio.sleep(1)
        except BaseException as e:
            logger.error("Captured exception", exception=e)
            pass


def get_queue_for_repo(owner: str, repo: str, installation_id: str) -> RepoWorker:
    id = f"{owner}/{repo}"
    rq = REPO_QUEUES.get(id)
    if rq is None:
        logger.info("could not find queue for repo")
        q = RepoQueue()
        task = asyncio.create_task(work_repo_queue(q))
        rq = RepoWorker(q=q, task=task)
        REPO_QUEUES[id] = rq
    return rq


async def event_processor(webhook_queue: "asyncio.Queue[Event]"):
    """
    - Lookup info for pull request
    - Should we add the pull request to be queued to updated/merged?

    - for a repos queue, while it's non-empty, loop.
    - take first PR, check it's mergability
        + update if necessary
        + remove from queue if no longer valid
        + merge PR
    """
    logger.info("event processor started")
    while True:
        try:
            github_event: "Event" = await webhook_queue.get()
            owner = github_event.repo_owner
            repo = github_event.repo_name
            pr_number = github_event.pull_request_number
            installation_id = github_event.installation_id
            log = logger.bind(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
            )
            log.info("pull event from queue for processing")
            repo_queue = get_queue_for_repo(
                owner=owner, repo=repo, installation_id=installation_id
            )
            res = await repo_queue.ingest(
                PR(
                    owner=owner,
                    repo=repo,
                    number=pr_number,
                    installation_id=installation_id,
                )
            )
            if isinstance(res, Retry):
                # add some delay for things to settle on Github's end
                await asyncio.sleep(1)
                webhook_queue.put_nowait(github_event)
        except Exception as e:
            log.warning("ignore exception", exec=e)
            pass


@app.on_event("startup")
async def startup():
    asyncio.create_task(event_processor(processing_queue))


@app.on_event("shutdown")
async def shutdown():
    ...
