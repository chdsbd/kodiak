import pytest

from kodiak.errors import PollForever
from kodiak.queries import MergeStateStatus
from kodiak.test_evaluation import create_api, create_mergeable, create_pull_request


@pytest.mark.asyncio
async def test_merge_blocked_for_unknown_reason() -> None:
    """
    If we get a pull request event with an unknown merge blockage, we requeue the PR.
    """
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    api = create_api()
    await mergeable(api=api, pull_request=pull_request)
    assert api.set_status.call_count == 1
    assert (
        "Retrying (Merging blocked by GitHub requirements)"
        in api.set_status.calls[0]["msg"]
    )
    assert api.requeue.call_count == 1
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 0


@pytest.mark.asyncio
async def test_merge_blocked_for_unknown_reason_merging() -> None:
    """
    If we're merging and we encounter an unknown merge blockage, we retry forever.
    """
    mergeable = create_mergeable()
    pull_request = create_pull_request()
    pull_request.mergeStateStatus = MergeStateStatus.BLOCKED
    api = create_api()
    with pytest.raises(PollForever):
        await mergeable(api=api, pull_request=pull_request, merging=True)
    assert api.set_status.call_count == 0
    assert api.requeue.call_count == 0
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 0
