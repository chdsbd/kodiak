from typing import Union

from fastapi import FastAPI
from kodiak.github import Webhook, events

app = FastAPI()

webhook = Webhook(app)


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


@webhook()
def event_handler(data: Union[events.PullRequestEvent]):
    raise NotImplementedError()
