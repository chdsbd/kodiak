import typing
import asyncio
from dataclasses import dataclass
from collections import defaultdict

import toml
from fastapi import FastAPI
import structlog

import kodiak
from kodiak.github import Webhook, events
from kodiak.queries import Client
from kodiak.evaluation import (
    evaluate_mergability,
    NotMergable,
    NeedsUpdate,
    CheckMergability,
)
from kodiak.handler import root_handler, create_git_revision_expression

app = FastAPI()

webhook = Webhook(app)
logger = structlog.get_logger()

CONFIG_FILE_PATH = ".kodiak.toml"

processing_queue: "asyncio.Queue[Event]" = asyncio.Queue()


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
    queue: "asyncio.Queue[QueuePR]" = asyncio.Queue()


REPO_QUEUES: typing.MutableMapping[str, RepoQueue] = defaultdict(RepoQueue)


class BehindTarget(Exception):
    pass


@dataclass
class QueuePR:
    repo_name: str
    repo_owner: str
    pull_request_id: int


def get_queue_for_repo(owner: str, name: str) -> RepoQueue:
    return REPO_QUEUES[f"{owner}/{name}"]


def add_to_queue(repo_name: str, repo_owner: str, pull_request_id: int):
    queue = get_queue_for_repo(owner=repo_owner, name=repo_name).queue
    logger.info("add to queue", queue=queue._queue)
    queue.put_nowait(
        QueuePR(
            repo_name=repo_name, repo_owner=repo_owner, pull_request_id=pull_request_id
        )
    )
    logger.info("added to queue", queue=queue._queue)


async def remove_from_queue(repo_name: str, repo_owner: str, pull_request_id: int):
    repo_queue = get_queue_for_repo(owner=repo_owner, name=repo_name)
    logger.info("remove from queue", queue=repo_queue.queue._queue)
    pr = QueuePR(
        repo_name=repo_name, repo_owner=repo_owner, pull_request_id=pull_request_id
    )
    queue = repo_queue.queue
    async with repo_queue.lock:
        try:
            typing.cast(typing.Any, queue)._queue.remove(pr)
        except ValueError:
            # pr wasn't in queue to remove
            pass
        logger.info("removed from queue", item=pr, queue=queue._queue)


async def event_processor(webhook_queue: "asyncio.Queue[Event]"):
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
            async with Client() as client:
                default_branch_name = await client.get_default_branch_name(
                    owner=owner, repo=repo, installation_id=installation_id
                )
                event_info = await client.get_event_info(
                    owner=owner,
                    repo=repo,
                    config_file_expression=create_git_revision_expression(
                        branch=default_branch_name, file_path=CONFIG_FILE_PATH
                    ),
                    pr_number=pr_number,
                    installation_id=installation_id,
                )

                if event_info.config_file is None:
                    log.warning("No configuration file found for repo.")
                    continue
                if event_info.pull_request is None:
                    log.warning("Could not find pull request")
                    continue
                if event_info.repo is None:
                    log.warning("Could not find repository")
                    continue

                try:
                    config = kodiak.config.V1.parse_toml(event_info.config_file)
                except (ValueError, toml.TomlDecodeError):
                    log.warning(
                        "Failure to parse toml configuration file",
                        config_path=CONFIG_FILE_PATH,
                    )
                    continue

                try:
                    evaluate_mergability(
                        config=config, pull_request=event_info.pull_request
                    )
                    # Enqueue for merge to add consistency in code paths when there
                    # are queues and not queues
                    add_to_queue(
                        repo_owner=owner, repo_name=repo, pull_request_id=pr_number
                    )
                except NotMergable as e:
                    log.info("not mergable", reasons=e.reasons)
                    await remove_from_queue(
                        repo_owner=owner, repo_name=repo, pull_request_id=pr_number
                    )
                except NeedsUpdate:
                    log.info("needs update")
                    add_to_queue(
                        repo_owner=owner, repo_name=repo, pull_request_id=pr_number
                    )
                except CheckMergability:
                    log.info("need to check mergability")
                    token = await client.get_token_for_install(
                        installation_id=installation_id
                    )
                    headers = dict(
                        Authorization=f"token {token}",
                        Accept="application/vnd.github.machine-man-preview+json",
                    )
                    url = (
                        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
                    )
                    res = await client.session.get(url, headers=headers)
                    if res.status_code > 300:
                        log.error("bad response", res=res, res_json=res.json())

                repo_queue = get_queue_for_repo(owner=owner, name=repo)
                queue = repo_queue.queue
                async with repo_queue.lock:
                    try:
                        first: QueuePR = typing.cast(typing.Any, queue)._queue[0]
                        token = await client.get_token_for_install(
                            installation_id=installation_id
                        )
                        headers = dict(
                            Authorization=f"token {token}",
                            Accept="application/vnd.github.machine-man-preview+json",
                        )
                        while True:
                            try:
                                url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge"
                                # TODO: Use configuration to determine merge method and other features of merge
                                # https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button
                                res = await client.session.put(
                                    url,
                                    headers=headers,
                                    json={"merge_method": "squash"},
                                )
                                if res.status_code == 405:
                                    raise BehindTarget()
                                if res.status_code > 300:
                                    log.error(
                                        "bad response", res=res, res_json=res.json()
                                    )
                                    raise Exception("Unhandled response")
                                log.debug("update pr request made")
                                break
                            except BehindTarget:
                                res = await client.session.post(
                                    f"https://api.github.com/repos/{owner}/{repo}/merges",
                                    json=dict(
                                        head=event_info.pull_request.baseRefName,
                                        base=event_info.pull_request.headRefName,
                                    ),
                                    headers=headers,
                                )
                                log.debug("update request made")
                                if res.status_code > 300:
                                    log.error(
                                        "bad response", res=res, res_json=res.json()
                                    )

                    except IndexError:
                        pass
        except Exception as e:
            log.warning("ignore exception", exec=e)
            pass


@app.on_event("startup")
async def startup():
    asyncio.create_task(event_processor(processing_queue))


@app.on_event("shutdown")
async def shutdown():
    ...
