from kodiak.events.base import Installation
from kodiak.events.check_run import (
    CheckRun,
    CheckRunEvent,
    Owner,
    PullRequest,
    PullRequestRepository,
    Ref,
    Repository,
)
from kodiak.queue import WebhookEvent, check_run


def test_ignore_external_pull_requests() -> None:
    """
    We should filter out pull requests that don't belong to our repository.
    """
    internal_repository_id = 554453
    internal_pull_request = PullRequest(
        number=123,
        base=Ref(ref="main", repo=PullRequestRepository(id=internal_repository_id)),
    )
    external_pull_request = PullRequest(
        number=534, base=Ref(ref="main", repo=PullRequestRepository(id=22))
    )
    event = CheckRunEvent(
        installation=Installation(id=69039045),
        check_run=CheckRun(
            name="circleci: build",
            pull_requests=[external_pull_request, internal_pull_request],
        ),
        repository=Repository(
            id=internal_repository_id, name="cake-api", owner=Owner(login="acme-corp")
        ),
    )
    assert list(check_run(event)) == [
        WebhookEvent(
            repo_owner="acme-corp",
            repo_name="cake-api",
            pull_request_number=internal_pull_request.number,
            installation_id=str(event.installation.id),
            target_name="main",
        )
    ]
