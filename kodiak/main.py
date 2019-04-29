from fastapi import FastAPI
from kodiak.github import Webhook, events

from . import handlers

app = FastAPI()

webhook = Webhook(app)


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@webhook()
def event_handler(data: events.PullRequestEvent):
    handlers.pull_request(data)
