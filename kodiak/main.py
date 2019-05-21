from __future__ import annotations
import typing
import asyncio
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto

import toml
from fastapi import FastAPI
import structlog
from sentry_asgi import SentryMiddleware
import sentry_sdk

import kodiak
from kodiak.github import Webhook, events
from kodiak.queries import (
    Client,
    EventInfoResponse,
    PullRequest,
    RepoInfo,
    BranchProtectionRule,
    PRReview,
    StatusContext,
    MergeMethod,
)
from kodiak import queries
from kodiak.evaluation import (
    mergable,
    NotQueueable,
    WaitingForChecks,
    MissingGithubMergabilityState,
    NeedsBranchUpdate,
)

sentry_sdk.init(dsn="https://8ccee0e2ac584ed78483ad51868db0a2@sentry.io/1464537")

app = FastAPI()
app.add_middleware(SentryMiddleware)

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
    sha = status_event.commit.sha
    owner = status_event.repository.owner.login
    repo = status_event.repository.name
    installation_id = str(status_event.installation.id)
    async with Client() as client:
        prs = await client.get_pull_requests_for_sha(
            owner=owner, repo=repo, installation_id=installation_id, sha=sha
        )
        if prs is None:
            logger.warning("problem finding prs for sha")
            return None
        for pr in prs:
            processing_queue.put_nowait(
                Event(
                    repo_owner=owner,
                    repo_name=repo,
                    pull_request_number=pr.number,
                    source_event=status_event,
                    installation_id=installation_id,
                )
            )


@webhook()
async def pr_review(review: events.PullRequestReviewEvent):
    assert review.installation
    # raise NotImplementedError


@dataclass
class RepoQueue:
    lock: asyncio.Lock = asyncio.Lock()
    queue: typing.Deque[PR] = deque()
    _waiters: typing.List[asyncio.Future] = field(default_factory=list)

    async def __getitem__(self, index: int) -> PR:
        try:
            return self.queue[index]
        except IndexError:
            fut: "asyncio.Future[PR]" = asyncio.get_event_loop().create_future()
            self._waiters.append(fut)
            return await fut

    async def enqueue(self, pr: PR) -> None:
        async with self.lock:
            if pr not in self.queue:
                # TODO: Is there a bug here by adding the item to the queue and returning it in the future?
                self.queue.append(pr)
                try:
                    fut = self._waiters.pop(0)
                    fut.set_result(pr)
                except IndexError:
                    pass

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
    branch_protection: BranchProtectionRule
    reviews: typing.List[PRReview] = field(default_factory=list)
    status_contexts: typing.List[StatusContext] = field(default_factory=list)
    valid_signature: bool = False
    valid_merge_methods: typing.List[MergeMethod] = field(default_factory=list)


class MergeabilityResponse(Enum):
    OK = auto()
    NEEDS_UPDATE = auto()
    NEED_REFRESH = auto()
    NOT_MERGEABLE = auto()
    WAIT = auto()


class MergeResults(Enum):
    OK = auto()
    CANNOT_MERGE = auto()
    API_FAILURE = auto()


@dataclass(init=False, repr=False, eq=False)
class PR:
    number: int
    owner: str
    repo: str
    installation_id: str
    log: structlog.BoundLogger
    Client: typing.Type[queries.Client] = field(
        default_factory=typing.Type[queries.Client]
    )

    def __eq__(self, b):
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
        Client: typing.Type[queries.Client] = queries.Client,
    ):
        self.number = number
        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        self.Client = Client
        self.log = logger.bind(repo=f"{owner}/{repo}#{number}")

    def __repr__(self) -> str:
        return f"<PR path='{self.owner}/{self.repo}#{self.number}'>"

    async def get_event(self) -> typing.Optional[PREventData]:
        async with self.Client() as client:
            default_branch_name = await client.get_default_branch_name(
                owner=self.owner, repo=self.repo, installation_id=self.installation_id
            )
            # TODO: Make this return a response we can immediately return
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
                self.log.warning("No configuration file found for repo.")
                return None
            if event_info.pull_request is None:
                self.log.warning("Could not find pull request")
                return None
            if event_info.repo is None:
                self.log.warning("Could not find repository")
                return None
            if event_info.branch_protection is None:
                self.log.warning("Missing required branch protection")
                return None
            try:
                config = kodiak.config.V1.parse_toml(event_info.config_file)
            except (ValueError, toml.TomlDecodeError):
                self.log.warning(
                    "Failure to parse toml configuration file",
                    config_path=CONFIG_FILE_PATH,
                )
                return None
            return PREventData(
                pull_request=event_info.pull_request,
                config=config,
                repo_info=event_info.repo,
                branch_protection=event_info.branch_protection,
                reviews=event_info.reviews,
                status_contexts=event_info.status_contexts,
                valid_signature=event_info.valid_signature,
                valid_merge_methods=event_info.valid_merge_methods,
            )

    async def mergability(
        self
    ) -> typing.Tuple[MergeabilityResponse, typing.Optional[kodiak.config.V1]]:
        event = await self.get_event()
        if event is None:
            return MergeabilityResponse.NOT_MERGEABLE, None
        try:
            mergable(
                config=event.config,
                pull_request=event.pull_request,
                branch_protection=event.branch_protection,
                reviews=event.reviews,
                contexts=event.status_contexts,
                valid_signature=event.valid_signature,
                valid_merge_methods=event.valid_merge_methods,
            )
            return MergeabilityResponse.OK, event.config
        except NotQueueable:
            return MergeabilityResponse.NOT_MERGEABLE, event.config
        except MissingGithubMergabilityState:
            return MergeabilityResponse.NEED_REFRESH, event.config
        except WaitingForChecks:
            return MergeabilityResponse.WAIT, event.config
        except NeedsBranchUpdate:
            return MergeabilityResponse.NEEDS_UPDATE, event.config

    async def update(self) -> None:
        async with self.Client() as client:
            event = await self.get_event()
            if event is None:
                self.log.warning("problem")
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
        m_res, config = await self.mergability()
        log = self.log.bind(merge_response=m_res)
        if m_res == MergeabilityResponse.NEEDS_UPDATE:
            await self.update()
        elif m_res == MergeabilityResponse.OK:
            pass
        elif m_res == MergeabilityResponse.NEED_REFRESH:
            pass
        elif m_res == MergeabilityResponse.WAIT:
            pass
        else:
            log.warning("Couldn't merge PR")
            return MergeResults.CANNOT_MERGE
        if config is None:
            return MergeResults.CANNOT_MERGE
        async with self.Client() as client:
            token = await client.get_token_for_install(
                installation_id=self.installation_id
            )
            headers = dict(
                Authorization=f"token {token}",
                Accept="application/vnd.github.machine-man-preview+json",
            )
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.number}/merge"
            res = await client.session.put(
                url, headers=headers, json={"merge_method": config.merge.method}
            )
            log.info("merge attempt", res=res, res_json=res.json())
            if res.status_code < 300:
                return MergeResults.OK
            return MergeResults.API_FAILURE


class Retry:
    pass


@dataclass
class RepoWorker:
    q: RepoQueue
    task: asyncio.Task
    Client: typing.Type[queries.Client] = queries.Client

    async def ingest(self, pr: PR) -> typing.Optional[Retry]:
        log = logger.bind(repo=f"{pr.owner}/{pr.repo}", pr_number=pr.number)
        # IF PR needs an update or can be merged, add it to queue
        mergability, _config = await pr.mergability()
        if mergability in (
            MergeabilityResponse.OK,
            MergeabilityResponse.NEEDS_UPDATE,
            MergeabilityResponse.WAIT,
        ):
            log.info("queuing", mergability=mergability)
            await self.q.enqueue(pr)
        elif mergability == MergeabilityResponse.NEED_REFRESH:
            log.info("Need to trigger update")
            async with self.Client() as client:
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
            log.info("cannot queue", mergability=mergability)
        return None


REPO_QUEUES: typing.MutableMapping[str, RepoWorker] = dict()
MERGE_SLEEP_SECONDS = 3


async def _work_repo_queue(q: RepoQueue):
    log = logger.bind(queue=q.queue)
    log.info("processing start")
    first = await q[0]
    log = log.bind(pr=first)
    async with q.lock:
        res = await first.merge()
        if res == MergeResults.OK:
            log.info("Merged. POP FROM QUEUE")
            q.queue.popleft()
        elif res == MergeResults.CANNOT_MERGE:
            log.info("Cannot merge. REMOVE FROM QUEUE")
            q.queue.popleft()
        else:
            await asyncio.sleep(MERGE_SLEEP_SECONDS)
            log.warning("problem merging")
        log.info("processing finished")


async def work_repo_queue(q: RepoQueue) -> typing.NoReturn:
    while True:
        try:
            await _work_repo_queue(q)
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
        github_event: "Event" = await webhook_queue.get()
        owner = github_event.repo_owner
        repo = github_event.repo_name
        pr_number = github_event.pull_request_number
        installation_id = github_event.installation_id
        log = logger.bind(
            installation_id=installation_id, owner=owner, repo=repo, pr_number=pr_number
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


@app.on_event("startup")
async def startup():
    asyncio.create_task(event_processor(processing_queue))


@app.on_event("shutdown")
async def shutdown():
    ...
