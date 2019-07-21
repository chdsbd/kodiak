import typing

import pytest
from pytest_mock import MockFixture
from starlette.testclient import TestClient

from kodiak import queries
from kodiak.config import (
    V1,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
)
from kodiak.pull_request import PR, MergeabilityResponse, get_merge_body
from kodiak.test_utils import wrap_future


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


MERGEABLE_RESPONSES = (
    MergeabilityResponse.OK,
    MergeabilityResponse.NEEDS_UPDATE,
    MergeabilityResponse.NEED_REFRESH,
    MergeabilityResponse.WAIT,
)

NOT_MERGEABLE_RESPONSES = (MergeabilityResponse.NOT_MERGEABLE,)


def test_mergeability_response_coverage() -> None:
    assert len(MergeabilityResponse) == len(
        MERGEABLE_RESPONSES + NOT_MERGEABLE_RESPONSES
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("labels,expected", [(["automerge"], True), ([], False)])
async def test_deleting_branch_after_merge(
    labels: typing.List[str],
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


def test_pr_get_merge_body_full(pull_request: queries.PullRequest) -> None:
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    title=MergeTitleStyle.pull_request_title,
                    body=MergeBodyStyle.pull_request_body,
                    include_pr_number=True,
                ),
            ),
        ),
        pull_request,
    )
    expected = dict(
        merge_method="squash",
        commit_title=pull_request.title + f" (#{pull_request.number})",
        commit_message=pull_request.body,
    )
    assert actual == expected


def test_pr_get_merge_body_empty(pull_request: queries.PullRequest) -> None:
    actual = get_merge_body(
        V1(version=1, merge=Merge(method=MergeMethod.squash)), pull_request
    )
    expected = dict(merge_method="squash")
    assert actual == expected


def test_get_merge_body_strip_html_comments(pull_request: queries.PullRequest) -> None:
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        V1(
            version=1,
            merge=Merge(
                method=MergeMethod.squash,
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, strip_html_comments=True
                ),
            ),
        ),
        pull_request,
    )
    expected = dict(merge_method="squash", commit_message="hello world")
    assert actual == expected
