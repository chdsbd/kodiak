"""
Tests for commit message "trailers".

Tested configuration options:
- merge.message.include_pull_request_url
- merge.message.include_coauthors
- merge.message.include_pull_request_author
"""

import pytest

from kodiak.config import V1, Merge, MergeBodyStyle, MergeMessage, MergeMethod
from kodiak.evaluation import MergeBody, get_merge_body
from kodiak.test_evaluation import (
    create_api,
    create_config,
    create_mergeable,
    create_pull_request,
)
from kodiak.tests.fixtures import create_commit


def test_get_merge_body_includes_pull_request_url() -> None:
    """
    Ensure that when the appropriate config option is set, we include the
    pull request url in the commit message.
    """
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body, include_pull_request_url=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65""",
    )
    assert actual == expected


def test_get_merge_body_includes_pull_request_url_github_default() -> None:
    """
    We should not set a commit message when merge.body = "github_default".
    """
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.github_default, include_pull_request_url=True
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(merge_method="squash", commit_message=None)
    assert actual == expected


def test_get_merge_body_includes_pull_request_url_with_coauthor() -> None:
    """
    Coauthor should appear after the pull request url
    """
    pull_request = create_pull_request()
    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_url=True,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="""\
# some description

https://github.com/example_org/example_repo/pull/65

Co-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>""",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_user() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: Barry Berkman <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_bot() -> None:
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Bot"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry[bot] <828352+barry[bot]@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_mannequin() -> None:
    """
    Test case where actor is not a User and Bot to see how we handle weird cases.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    pull_request.author.name = None
    pull_request.author.type = "Mannequin"

    actual = get_merge_body(
        config=V1(
            version=1,
            merge=Merge(
                message=MergeMessage(
                    body=MergeBodyStyle.pull_request_body,
                    include_pull_request_author=True,
                )
            ),
        ),
        pull_request=pull_request,
        merge_method=MergeMethod.squash,
        commits=[],
    )
    expected = MergeBody(
        merge_method="squash",
        commit_message="hello world\n\nCo-authored-by: barry <828352+barry@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_pull_request_author_invalid_body_style() -> None:
    """
    We only include trailers MergeBodyStyle.pull_request_body and
    MergeBodyStyle.empty. Verify we don't include trailers for
    MergeBodyStyle.github_default.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.include_pull_request_author = True

    config.merge.message.body = MergeBodyStyle.github_default
    actual = get_merge_body(
        config=config,
        pull_request=pull_request,
        merge_method=MergeMethod.merge,
        commits=[],
    )
    expected = MergeBody(merge_method="merge", commit_message=None)
    assert actual == expected


def test_get_merge_body_include_coauthors() -> None:
    """
    Verify we include coauthor trailers for MergeBodyStyle.pull_request_body.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.body = MergeBodyStyle.pull_request_body
    config.merge.message.include_coauthors = True
    config.merge.message.include_pull_request_author = False

    actual = get_merge_body(
        config=config,
        merge_method=MergeMethod.merge,
        pull_request=pull_request,
        commits=[
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            create_commit(
                database_id=590434, name="Maeve Millay", login="maeve-m", type="Bot"
            ),
            # we default to the login when name is None.
            create_commit(
                database_id=771233, name=None, login="d-abernathy", type="Bot"
            ),
            # without a databaseID the commit author will be ignored.
            create_commit(database_id=None, name=None, login="william", type="User"),
            # duplicate should be ignored.
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            # merge commits should be ignored. merge commits will have more than
            # one parent.
            create_commit(
                database_id=1,
                name="Arnold Weber",
                login="arnold",
                type="User",
                parents=2,
            ),
            # pull request author should be ignored when
            # include_pull_request_author is not enabled
            create_commit(
                database_id=pull_request.author.databaseId,
                name="Joe PR Author",
                login="j-author",
                type="User",
            ),
        ],
    )
    expected = MergeBody(
        merge_method="merge",
        commit_message="hello world\n\nCo-authored-by: Bernard Lowe <9023904+b-lowe@users.noreply.github.com>\nCo-authored-by: Maeve Millay <590434+maeve-m[bot]@users.noreply.github.com>\nCo-authored-by: d-abernathy[bot] <771233+d-abernathy[bot]@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_coauthors_include_pr_author() -> None:
    """
    We should include the pull request author when configured.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.body = MergeBodyStyle.pull_request_body
    config.merge.message.include_coauthors = True
    config.merge.message.include_pull_request_author = True

    actual = get_merge_body(
        config=config,
        merge_method=MergeMethod.merge,
        pull_request=pull_request,
        commits=[
            create_commit(
                database_id=9023904, name="Bernard Lowe", login="b-lowe", type="User"
            ),
            # we should ignore a duplicate entry for the PR author when
            # include_pull_request_author is enabled.
            create_commit(
                database_id=pull_request.author.databaseId,
                name=pull_request.author.name,
                login=pull_request.author.login,
                type=pull_request.author.type,
            ),
        ],
    )
    expected = MergeBody(
        merge_method="merge",
        commit_message=f"hello world\n\nCo-authored-by: {pull_request.author.name} <{pull_request.author.databaseId}+{pull_request.author.login}@users.noreply.github.com>\nCo-authored-by: Bernard Lowe <9023904+b-lowe@users.noreply.github.com>",
    )
    assert actual == expected


def test_get_merge_body_include_coauthors_invalid_body_style() -> None:
    """
    We only include trailers for MergeBodyStyle.pull_request_body and MergeBodyStyle.empty. Verify we don't add coauthor trailers for MergeBodyStyle.github_default.
    """
    pull_request = create_pull_request()
    pull_request.body = "hello world"
    config = create_config()
    config.merge.message.include_coauthors = True
    config.merge.message.body = MergeBodyStyle.github_default
    actual = get_merge_body(
        config=config,
        pull_request=pull_request,
        merge_method=MergeMethod.merge,
        commits=[
            create_commit(database_id=9023904, name="", login="b-lowe", type="User"),
            create_commit(
                database_id=590434, name="Maeve Millay", login="maeve-m", type="Bot"
            ),
        ],
    )
    expected = MergeBody(merge_method="merge", commit_message=None)
    assert actual == expected


@pytest.mark.asyncio
async def test_mergeable_include_coauthors() -> None:
    """
    Include coauthors should attach coauthor when `merge.message.body = "pull_request_body"`
    """
    mergeable = create_mergeable()
    config = create_config()
    config.merge.message.include_coauthors = True

    for body_style, commit_message in (
        (
            MergeBodyStyle.pull_request_body,
            "# some description\n\nCo-authored-by: Barry Block <73213123+b-block@users.noreply.github.com>",
        ),
        (
            MergeBodyStyle.empty,
            "Co-authored-by: Barry Block <73213123+b-block@users.noreply.github.com>",
        ),
    ):
        config.merge.message.body = body_style
        api = create_api()
        await mergeable(
            api=api,
            config=config,
            commits=[
                create_commit(
                    database_id=73213123,
                    name="Barry Block",
                    login="b-block",
                    type="User",
                )
            ],
            merging=True,
        )
        assert api.set_status.call_count == 2
        assert "attempting to merge PR" in api.set_status.calls[0]["msg"]
        assert api.set_status.calls[1]["msg"] == "merge complete 🎉"

        assert api.merge.call_count == 1
        assert commit_message == api.merge.calls[0]["commit_message"]
        assert api.update_branch.call_count == 0
        assert api.queue_for_merge.call_count == 0
        assert api.dequeue.call_count == 0
