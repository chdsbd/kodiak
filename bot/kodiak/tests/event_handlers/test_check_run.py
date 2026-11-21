from __future__ import annotations

from typing import AsyncIterator, List, Optional

import pytest
from pytest_mock import MockFixture

from kodiak import pull_request
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
from kodiak.pull_request import EventInfoResponse
from kodiak.push_filter import get_ignored_pull_request_key, save_pull_request_ignored
from kodiak.queue import (
    WEBHOOK_QUEUE_NAMES,
    WebhookEvent,
    check_run,
    get_installation_webhook_queue_name,
    handle_webhook_event,
    ingest_check_run,
)
from kodiak.redis_client import create_connection
from kodiak.test_pull_request import create_event, noop
from kodiak.tests.fixtures import requires_redis


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


class FakeQueue:
    def __init__(self) -> None:
        self.events: List[WebhookEvent] = []

    async def enqueue(self, *, event: WebhookEvent, low_priority: bool = False) -> None:
        self.events.append(event)

    async def enqueue_for_repo(
        self, *, event: WebhookEvent, first: bool
    ) -> Optional[int]:
        raise NotImplementedError


@pytest.fixture
async def push_filter_redis(mocker: MockFixture) -> AsyncIterator[None]:
    # use our own client because the shared one may hold connections from other
    # tests' event loops.
    redis = create_connection()
    mocker.patch("kodiak.push_filter.redis_bot", redis)
    mocker.patch("kodiak.queue.redis_bot", redis)
    yield
    await redis.delete(get_installation_webhook_queue_name(69039045))
    await redis.srem(WEBHOOK_QUEUE_NAMES, get_installation_webhook_queue_name(69039045))
    for number in (123, 124):
        await redis.delete(
            get_ignored_pull_request_key(
                installation_id="69039045",
                owner="acme-corp",
                repo="cake-api",
                number=number,
            )
        )
    await redis.close()


@requires_redis
async def test_check_run_skips_pull_requests_kodiak_wont_act_on(
    push_filter_redis: None,
) -> None:
    """
    A check run can't change anything for a pull request Kodiak ignores. Pull
    requests we haven't evaluated recently are still queued.
    """
    await save_pull_request_ignored(
        installation_id="69039045",
        owner="acme-corp",
        repo="cake-api",
        number=123,
        ignored=True,
    )
    repository_id = 554453
    event = CheckRunEvent(
        installation=Installation(id=69039045),
        check_run=CheckRun(
            name="circleci: build",
            pull_requests=[
                PullRequest(
                    number=number,
                    base=Ref(ref="main", repo=PullRequestRepository(id=repository_id)),
                )
                for number in (123, 124)
            ],
        ),
        repository=Repository(
            id=repository_id, name="cake-api", owner=Owner(login="acme-corp")
        ),
    )
    queue = FakeQueue()

    await handle_webhook_event(queue, "check_run", event.dict())

    assert [event.pull_request_number for event in queue.events] == [124]


class FakeEventInfoClient:
    def __init__(self, event: EventInfoResponse) -> None:
        self.event = event

    async def __aenter__(self) -> FakeEventInfoClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_event_info(self, pr_number: int) -> EventInfoResponse:
        return self.event


@requires_redis
async def test_check_run_queues_pull_request_after_automerge_label_added(
    mocker: MockFixture, push_filter_redis: None
) -> None:
    """
    Adding the automerge label triggers an evaluation, which forgets that we
    ignored the pull request, so its check runs are queued again.
    """
    event = create_event()
    event.pull_request.labels = []
    mocker.patch("kodiak.pull_request.Client", return_value=FakeEventInfoClient(event))

    async def get_pr() -> None:
        await pull_request.get_pr(
            install="69039045",
            owner="acme-corp",
            repo="cake-api",
            number=123,
            dequeue_callback=noop,
            requeue_callback=noop,
            queue_for_merge_callback=noop,
        )

    def check_run_payload() -> dict[str, object]:
        return CheckRunEvent(
            installation=Installation(id=69039045),
            check_run=CheckRun(
                name="circleci: build",
                pull_requests=[
                    PullRequest(
                        number=123,
                        base=Ref(ref="main", repo=PullRequestRepository(id=554453)),
                    )
                ],
            ),
            repository=Repository(
                id=554453, name="cake-api", owner=Owner(login="acme-corp")
            ),
        ).dict()

    await get_pr()
    unlabeled = FakeQueue()
    await handle_webhook_event(unlabeled, "check_run", check_run_payload())

    event.pull_request.labels = ["automerge"]
    await get_pr()
    labeled = FakeQueue()
    await handle_webhook_event(labeled, "check_run", check_run_payload())

    assert unlabeled.events == []
    assert [event.pull_request_number for event in labeled.events] == [123]


@requires_redis
async def test_ingest_check_run_queues_each_pull_request_once(
    push_filter_redis: None,
) -> None:
    """
    Busy repositories report hundreds of check runs for a pull request within
    minutes. Ingest adds them to the webhook queue, which holds each pull
    request once.
    """
    await save_pull_request_ignored(
        installation_id="69039045",
        owner="acme-corp",
        repo="cake-api",
        number=123,
        ignored=True,
    )
    repository_id = 554453
    payload = CheckRunEvent(
        installation=Installation(id=69039045),
        check_run=CheckRun(
            name="circleci: build",
            pull_requests=[
                PullRequest(
                    number=number,
                    base=Ref(ref="main", repo=PullRequestRepository(id=repository_id)),
                )
                for number in (123, 124)
            ],
        ),
        repository=Repository(
            id=repository_id, name="cake-api", owner=Owner(login="acme-corp")
        ),
    ).dict()

    queued = [await ingest_check_run(payload) for _ in range(3)]

    redis = create_connection()
    queue_name = get_installation_webhook_queue_name(69039045)
    events = await redis.zrange(queue_name, 0, -1)
    assert await redis.sismember(WEBHOOK_QUEUE_NAMES, queue_name)
    await redis.close()
    assert queued == [1, 1, 1]
    assert [WebhookEvent.parse_raw(event).pull_request_number for event in events] == [
        124
    ]


async def test_ingest_check_run_without_pull_requests() -> None:
    """
    Check runs on the default branch or on forks have no pull requests, so
    there's nothing to queue.
    """
    payload = CheckRunEvent(
        installation=Installation(id=69039045),
        check_run=CheckRun(name="circleci: build", pull_requests=[]),
        repository=Repository(
            id=554453, name="cake-api", owner=Owner(login="acme-corp")
        ),
    ).dict()

    assert await ingest_check_run(payload) == 0
