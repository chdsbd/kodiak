from fastapi import FastAPI
from kodiak.github import Webhook, events

from kodiak.handler import base_handler

app = FastAPI()

webhook = Webhook(app)


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@webhook()
async def pr_event(pr: events.PullRequestEvent):
    await base_handler(
        owner=pr.repository.owner.login, repo=pr.repository.name, pr_number=pr.number
    )
