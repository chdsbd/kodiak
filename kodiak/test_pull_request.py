import typing
from pathlib import Path

import pytest
import requests_async as http
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
from kodiak.queries import EventInfoResponse


def test_read_main(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "OK"


@pytest.fixture
def create_pr(event_response: EventInfoResponse) -> typing.Callable:
    def create(mergeable_response: MergeabilityResponse) -> PR:
        class FakePR(PR):
            async def mergeability(
                self
            ) -> typing.Tuple[MergeabilityResponse, EventInfoResponse]:
                return mergeable_response, event_response

        return FakePR(number=123, owner="tester", repo="repo", installation_id="abc")

    return create


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


@pytest.fixture
def gh_client(
    event_response: queries.EventInfoResponse, mock_client: typing.Type[queries.Client]
) -> typing.Type[queries.Client]:
    class MockClient(mock_client):  # type: ignore
        async def get_default_branch_name(
            *args: typing.Any, **kwargs: typing.Any
        ) -> str:
            return "master"

        async def get_event_info(
            *args: typing.Any, **kwargs: typing.Any
        ) -> queries.EventInfoResponse:
            return event_response

        def generate_jwt(*args: typing.Any, **kwargs: typing.Any) -> str:
            return "abc"

        async def get_token_for_install(*args: typing.Any, **kwargs: typing.Any) -> str:
            return "abc"

    return MockClient


@pytest.mark.asyncio
@pytest.mark.parametrize("labels,expected", [(["automerge"], True), ([], False)])
async def test_deleting_branch_after_merge(
    labels: typing.List[str], expected: bool, event_response: queries.EventInfoResponse
) -> None:
    """
    ensure client.delete_branch is called when a PR that is already merged is
    evaluated.
    """

    event_response.pull_request.state = queries.PullRequestState.MERGED
    event_response.pull_request.labels = labels
    event_response.config.merge.delete_branch_on_merge = True

    class FakePR(PR):
        async def get_event(self) -> typing.Optional[queries.EventInfoResponse]:
            return event_response

        async def set_status(
            self, *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            return None

    called = False

    class FakeClient(queries.Client):
        def __init__(
            self,
            owner: str,
            repo: str,
            installation_id: str,
            token: typing.Optional[str] = None,
            private_key: typing.Optional[str] = None,
            private_key_path: typing.Optional[Path] = None,
            app_identifier: typing.Optional[str] = None,
        ):
            self.token = token
            self.private_key = private_key
            self.private_key_path = private_key_path
            self.app_identifier = app_identifier
            self.session = http.Session()

        async def delete_branch(self, branch: str) -> bool:
            nonlocal called
            called = True
            return True

    pr = FakePR(
        number=123,
        owner="tester",
        repo="repo",
        installation_id="abc",
        Client=FakeClient,
    )

    await pr.mergeability()

    assert called == expected


def test_pr(gh_client: typing.Type[queries.Client]) -> None:
    a = PR(
        number=123,
        owner="ghost",
        repo="ghost",
        installation_id="abc123",
        Client=gh_client,
    )
    b = PR(number=123, owner="ghost", repo="ghost", installation_id="abc123")
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
