"""
Tests for the merge.message.{cut_body_before,cut_body_after} configuration options.
"""

from kodiak.config import V1, Merge, MergeBodyStyle, MergeMessage, MergeMethod
from kodiak.evaluation import MergeBody, get_merge_body
from kodiak.test_evaluation import create_pull_request


def test_get_merge_body_cut_body_after() -> None:
    """
    Basic check of cut_body_after removing content.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_after="<!-- testing -->",
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello <!-- testing -->")
    assert actual == expected


def test_get_merge_body_cut_body_and_text_after() -> None:
    """
    Verify that the separator is also gone after removing content.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_after="<!-- testing -->",
                    cut_body_and_text=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello ")
    assert actual == expected


def test_get_merge_body_cut_body_and_text_before() -> None:
    """
    Verify that the separator is also gone after removing content.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_before="<!-- testing -->",
                    cut_body_and_text=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="world")
    assert actual == expected


def test_get_merge_body_cut_body_after_strip_html() -> None:
    """
    We should be able to use strip_html_comments with cut_body_after.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_after="<!-- testing -->",
                    strip_html_comments=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello ")
    assert actual == expected


def test_get_merge_body_cut_body_after_multiple_markers() -> None:
    """
    We should choose the first substring matching cut_body_after.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world<!-- testing --> 123"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_after="<!-- testing -->",
                    strip_html_comments=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="hello ")
    assert actual == expected


def test_get_merge_body_cut_body_after_no_match_found() -> None:
    """
    Ensure we don't edit the message if there isn't any match found with
    cut_body_after.
    """
    pull_request = create_pull_request()
    pr_body = "hello <!-- foo -->world<!-- bar --> 123"
    pull_request.body = pr_body
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_after="<!-- buzz -->",
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message=pr_body)
    assert actual == expected


def test_get_merge_body_cut_body_before_no_match_found() -> None:
    """
    Ensure we don't edit the message if there isn't any match found with
    cut_body_before.
    """
    pull_request = create_pull_request()
    pr_body = "hello <!-- foo -->world<!-- bar --> 123"
    pull_request.body = pr_body
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_before="<!-- buzz -->",
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message=pr_body)
    assert actual == expected


def test_get_merge_body_cut_body_before() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_before="<!-- testing -->",
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="<!-- testing -->world")
    assert actual == expected


def test_get_merge_body_cut_body_before_strip_html() -> None:
    """
    We should be able to use strip_html_comments with cut_body_before.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_before="<!-- testing -->",
                    strip_html_comments=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="world")
    assert actual == expected


def test_get_merge_body_cut_body_before_multiple_markers() -> None:
    """
    We should choose the first substring matching cut_body_before.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello <!-- testing -->world<!-- testing --> 123"
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    cut_body_before="<!-- testing -->",
                    strip_html_comments=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message="world 123")
    assert actual == expected
