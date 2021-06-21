"""
Tests for general merge.message configuration options.

Some configuration options have their own specific test files.
"""

from kodiak.config import (
    V1,
    Merge,
    MergeBodyStyle,
    MergeMessage,
    MergeMethod,
    MergeTitleStyle,
)
from kodiak.evaluation import MergeBody, get_merge_body
from kodiak.test_evaluation import create_pull_request


def test_pr_get_merge_body_full() -> None:
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    title=MergeTitleStyle.pull_request_title,
                    body=MergeBodyStyle.pull_request_body,
                    include_pr_number=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_title=pull_request.title + f" (#{pull_request.number})",
        commit_message=pull_request.body,
    )
    assert expected == actual


def test_pr_get_merge_body_empty() -> None:
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(version=1),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash")
    assert actual == expected


def test_get_merge_body_strip_html_comments() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, strip_html_comments=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello world")
    assert actual == expected


def test_get_merge_body_empty() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    actual = get_merge_body(
        config=V1(
            version=1, merge=Merge(message=MergeMessage(body=MergeBodyStyle.empty))
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="")
    assert actual == expected
