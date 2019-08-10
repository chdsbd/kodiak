import pytest
from pytest_mock import MockFixture

from kodiak.pull_request import PR
from kodiak.queue import update_pr_with_retry
from kodiak.test_utils import wrap_future


@pytest.mark.asyncio
async def test_update_pr_with_retry_success(pr: PR, mocker: MockFixture) -> None:
    mocker.patch("kodiak.queue.asyncio.sleep", return_value=wrap_future(None))
    mocker.patch.object(pr, "update", return_value=wrap_future(True))
    res = await update_pr_with_retry(pr)
    assert res


@pytest.mark.asyncio
async def test_update_pr_with_retry_failure(pr: PR, mocker: MockFixture) -> None:
    asyncio_sleep = mocker.patch(
        "kodiak.queue.asyncio.sleep", return_value=wrap_future(None)
    )
    mocker.patch.object(pr, "update", return_value=wrap_future(False))
    res = await update_pr_with_retry(pr)
    assert not res

    assert asyncio_sleep.call_count == 5

@pytest.mark.asyncio
async def test_process_webhook_event_update_branch():
    """
    Verify that config.merge.update_branch_immediately triggers branch update immediately
    """
    assert False
