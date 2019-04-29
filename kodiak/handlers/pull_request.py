from kodiak.github import events
from kodiak.handlers.base_handler import base_handler


async def handler(pr: events.PullRequestEvent) -> None:
    await base_handler(
        owner=pr.repository.owner.login, repo=pr.repository.name, pr_number=pr.number
    )
