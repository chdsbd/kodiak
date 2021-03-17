import pytest

from kodiak.config import MergeMethod
from kodiak.test_evaluation import create_api, create_config, create_mergeable


@pytest.mark.asyncio
async def test_rebase_merge_fast_forward() -> None:
    """
    Happy case.

    """
    mergeable = create_mergeable()
    api = create_api()
    config = create_config()
    config.merge.method = MergeMethod.rebase_fast_forward
    await mergeable(api=api, config=config, merging=True)

    assert api.update_ref.call_count == 1
    assert api.merge.call_count == 0
    assert api.set_status.call_count == 2
    assert "(merging)" in api.set_status.calls[0]["msg"]
    assert api.queue_for_merge.call_count == 0
    assert api.dequeue.call_count == 0

