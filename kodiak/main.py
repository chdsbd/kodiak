import typing
from fastapi import FastAPI
from kodiak.github import Webhook, events
import asyncio

from kodiak.handler import root_handler

app = FastAPI()

webhook = Webhook(app)


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@webhook()
async def pr_event(pr: events.PullRequestEvent):
    assert pr.installation is not None
    await root_handler(
        owner=pr.repository.owner.login,
        repo=pr.repository.name,
        pr_number=pr.number,
        installation_id=pr.installation.id,
    )


@webhook()
async def check_run(check_run_event: events.CheckRunEvent):
    assert check_run_event.installation
    owner = check_run_event.repository.owner.login
    repo = check_run_event.repository.name
    installation_id = check_run_event.installation.id
    await asyncio.gather(
        *[
            root_handler(
                owner=owner,
                repo=repo,
                pr_number=pr.number,
                installation_id=installation_id,
            )
            for pr in check_run_event.check_run.pull_requests
        ]
    )


@webhook()
async def status_event(status_event: events.StatusEvent):
    assert status_event.installation
    # TODO: Get PRs for sha and do something like we do with check_run


@webhook()
async def pr_review(review: events.PullRequestReviewEvent):
    assert review.installation
