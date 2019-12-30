from typing import List

import pytest
from pytest_mock import MockFixture
from requests_async import Response

from kodiak import queries
from kodiak.config import (
    V1,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
)
from kodiak.errors import MissingSkippableChecks
from kodiak.pull_request import PR, MergeabilityResponse
from kodiak.test_utils import wrap_future

MERGEABLE_RESPONSES = (
    MergeabilityResponse.OK,
    MergeabilityResponse.NEEDS_UPDATE,
    MergeabilityResponse.NEED_REFRESH,
    MergeabilityResponse.WAIT,
)

NOT_MERGEABLE_RESPONSES = (
    MergeabilityResponse.NOT_MERGEABLE,
    MergeabilityResponse.SKIPPABLE_CHECKS,
)


def test_mergeability_response_coverage() -> None:
    assert len(MergeabilityResponse) == len(
        MERGEABLE_RESPONSES + NOT_MERGEABLE_RESPONSES
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("labels,expected", [(["automerge"], True), ([], False)])
async def test_deleting_branch_after_merge(
    labels: List[str],
    expected: bool,
    event_response: queries.EventInfoResponse,
    mocker: MockFixture,
) -> None:
    """
    ensure client.delete_branch is called when a PR that is already merged is
    evaluated.
    """

    event_response.pull_request.state = queries.PullRequestState.MERGED
    event_response.pull_request.labels = labels
    assert isinstance(event_response.config, V1)
    event_response.config.merge.delete_branch_on_merge = True

    mocker.patch.object(PR, "get_event", return_value=wrap_future(event_response))
    mocker.patch.object(PR, "set_status", return_value=wrap_future(None))

    delete_branch = mocker.patch.object(
        queries.Client, "delete_branch", return_value=wrap_future(True)
    )

    pr = PR(
        number=123,
        owner="tester",
        repo="repo",
        installation_id="abc",
        client=queries.Client(owner="tester", repo="repo", installation_id="abc"),
    )

    await pr.mergeability()

    assert delete_branch.called == expected


@pytest.mark.asyncio
async def test_deleting_branch_not_called_for_fork(
    event_response: queries.EventInfoResponse, mocker: MockFixture
) -> None:
    """
    we cannot delete branches of forks so we should not hit the delete_branch query.
    """

    event_response.pull_request.state = queries.PullRequestState.MERGED
    event_response.pull_request.isCrossRepository = True
    event_response.pull_request.labels = ["automerge"]
    assert isinstance(event_response.config, V1)
    event_response.config.merge.delete_branch_on_merge = True

    mocker.patch.object(PR, "get_event", return_value=wrap_future(event_response))
    mocker.patch.object(PR, "set_status", return_value=wrap_future(None))

    delete_branch = mocker.patch.object(
        queries.Client, "delete_branch", return_value=wrap_future(True)
    )

    pr = PR(
        number=123,
        owner="tester",
        repo="repo",
        installation_id="abc",
        client=queries.Client(owner="tester", repo="repo", installation_id="abc"),
    )

    await pr.mergeability()

    assert delete_branch.called is False


def test_pr(api_client: queries.Client) -> None:
    a = PR(
        number=123,
        owner="ghost",
        repo="ghost",
        installation_id="abc123",
        client=api_client,
    )
    b = PR(
        number=123,
        owner="ghost",
        repo="ghost",
        installation_id="abc123",
        client=api_client,
    )
    assert a == b, "equality should work even though they have different clients"

    from collections import deque

    assert a in deque([b])


@pytest.mark.asyncio
async def test_attempting_to_notify_pr_author_with_no_automerge_label(
    api_client: queries.Client,
    mocker: MockFixture,
    event_response: queries.EventInfoResponse,
) -> None:
    """
    ensure that when Kodiak encounters a merge conflict it doesn't notify
    the user if an automerge label isn't required.
    """

    pr = PR(
        number=123,
        owner="ghost",
        repo="ghost",
        installation_id="abc123",
        client=api_client,
    )
    assert isinstance(event_response.config, V1)
    event_response.config.merge.require_automerge_label = False
    pr.event = event_response

    create_comment = mocker.patch.object(
        PR, "create_comment", return_value=wrap_future(None)
    )
    # mock to ensure we have a chance of hitting the create_comment call
    mocker.patch.object(PR, "delete_label", return_value=wrap_future(True))

    assert await pr.notify_pr_creator() is False
    assert not create_comment.called


@pytest.mark.asyncio
async def test_pr_update_ok(
    mocker: MockFixture, event_response: queries.EventInfoResponse, pr: PR
) -> None:
    """
    Update should return true on success
    """
    mocker.patch.object(PR, "get_event", return_value=wrap_future(event_response))
    res = Response()
    res.status_code = 200
    mocker.patch(
        "kodiak.pull_request.queries.Client.update_branch",
        return_value=wrap_future(res),
    )

    res = await pr.update()
    assert res, "should be true when we have a successful call"


@pytest.mark.asyncio
async def test_pr_update_bad_merge(
    mocker: MockFixture, event_response: queries.EventInfoResponse, pr: PR
) -> None:
    """
    Update should return false on an error
    """
    mocker.patch.object(PR, "get_event", return_value=wrap_future(event_response))
    res = Response()
    res.status_code = 409
    res._content = b"{}"
    mocker.patch(
        "kodiak.pull_request.queries.Client.update_branch",
        return_value=wrap_future(res),
    )

    res = await pr.update()
    assert not res


@pytest.mark.asyncio
async def test_pr_update_missing_event(mocker: MockFixture, pr: PR) -> None:
    """
    Return False if get_event res is missing
    """
    mocker.patch.object(PR, "get_event", return_value=wrap_future(None))

    res = await pr.update()
    assert not res


@pytest.mark.asyncio
async def test_mergeability_missing_skippable_checks(
    mocker: MockFixture, event_response: queries.EventInfoResponse, pr: PR
) -> None:
    mocker.patch.object(PR, "get_event", return_value=wrap_future(event_response))
    mergeable = mocker.patch("kodiak.pull_request.mergeable")
    mergeable.side_effect = MissingSkippableChecks([])
    mocker.patch.object(PR, "set_status", return_value=wrap_future(None))
    res, event = await pr.mergeability()
    assert res == MergeabilityResponse.SKIPPABLE_CHECKS
