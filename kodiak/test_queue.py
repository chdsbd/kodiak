from unittest.mock import MagicMock

import pytest
import structlog
from pytest_mock import MockFixture

from kodiak.config import V1
from kodiak.pull_request import PR, EventInfoResponse, MergeabilityResponse
from kodiak.queue import update_pr_immediately_if_configured, update_pr_with_retry
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


@pytest.fixture
def mock_pull_request(mocker: MockFixture) -> MagicMock:
    pr = mocker.MagicMock(PR)()
    # handle `TypeError: object MagicMock can't be used in 'await' expression`
    pr.set_status.return_value = wrap_future(None)
    return pr


@pytest.fixture
def mock_logger(mocker: MockFixture) -> structlog.BoundLogger:
    return mocker.MagicMock(structlog.BoundLogger)()


@pytest.mark.asyncio
async def test_update_pr_immediately_if_configured_successful_update(
    mocker: MockFixture,
    mock_pull_request: MagicMock,
    mock_logger: structlog.BoundLogger,
    event_response: EventInfoResponse,
) -> None:
    """
    Test successful case where merge.update_branch_immediately is set and
    updating PR succeeds
    """
    update_pr_with_retry = mocker.patch(
        "kodiak.queue.update_pr_with_retry", return_value=wrap_future(True)
    )
    assert isinstance(event_response.config, V1)
    assert isinstance(event_response.config, V1)
    event_response.config.merge.update_branch_immediately = True
    await update_pr_immediately_if_configured(
        m_res=MergeabilityResponse.NEEDS_UPDATE,
        event=event_response,
        pull_request=mock_pull_request,
        log=mock_logger,
    )
    assert update_pr_with_retry.call_count == 1
    assert mock_pull_request.set_status.call_count == 0


@pytest.mark.asyncio
async def test_update_pr_immediately_if_configured_failed_update(
    mocker: MockFixture,
    mock_pull_request: MagicMock,
    mock_logger: structlog.BoundLogger,
    event_response: EventInfoResponse,
) -> None:
    """
    Test case where merge.update_branch_immediately is set and updating PR fails
    """
    update_pr_with_retry = mocker.patch(
        "kodiak.queue.update_pr_with_retry", return_value=wrap_future(False)
    )
    assert isinstance(event_response.config, V1)
    event_response.config.merge.update_branch_immediately = True
    await update_pr_immediately_if_configured(
        m_res=MergeabilityResponse.NEEDS_UPDATE,
        event=event_response,
        pull_request=mock_pull_request,
        log=mock_logger,
    )
    assert update_pr_with_retry.call_count == 1
    assert (
        mock_pull_request.set_status.call_count == 1
    ), "we should call set_status on a failure"


@pytest.mark.asyncio
async def test_update_pr_immediately_if_configured_no_config(
    mocker: MockFixture,
    mock_pull_request: MagicMock,
    mock_logger: structlog.BoundLogger,
    event_response: EventInfoResponse,
) -> None:
    """
    If merge.update_branch_immediately is not set, we shouldn't update the PR
    """
    update_pr_with_retry = mocker.patch(
        "kodiak.queue.update_pr_with_retry", return_value=wrap_future(True)
    )
    assert isinstance(event_response.config, V1)
    event_response.config.merge.update_branch_immediately = False
    await update_pr_immediately_if_configured(
        m_res=MergeabilityResponse.NEEDS_UPDATE,
        event=event_response,
        pull_request=mock_pull_request,
        log=mock_logger,
    )
    assert update_pr_with_retry.call_count == 0
    assert (
        mock_pull_request.set_status.call_count == 0
    ), "we shouldn't hit these functions"
