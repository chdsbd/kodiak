from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union, cast

import toml
from pydantic import BaseModel, ValidationError, validator


class MergeMethod(str, Enum):
    merge = "merge"
    squash = "squash"
    rebase = "rebase"


class MergeTitleStyle(Enum):
    github_default = "github_default"
    pull_request_title = "pull_request_title"


class MergeBodyStyle(Enum):
    github_default = "github_default"
    pull_request_body = "pull_request_body"
    empty = "empty"


class BodyText(Enum):
    plain_text = "plain_text"
    markdown = "markdown"
    html = "html"


class MergeMessage(BaseModel):
    """
    https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button
    """

    title: MergeTitleStyle = MergeTitleStyle.github_default
    body: MergeBodyStyle = MergeBodyStyle.github_default
    include_pr_number: bool = True
    body_type: BodyText = BodyText.markdown
    strip_html_comments: bool = False


class Merge(BaseModel):
    # label to enable merging of pull request.
    automerge_label: str = "automerge"
    # if disabled, kodiak won't require a label to queue a PR for merge
    require_automerge_label: bool = True
    # regex to match against title and block merging. Set to empty string to
    # disable check.
    blacklist_title_regex: str = "^WIP:.*"
    # labels to block merging of pull request
    blacklist_labels: List[str] = []
    # action to take when attempting to merge PR. An error will occur if method
    # is disabled for repository
    method: MergeMethod = MergeMethod.merge
    # delete branch when PR is merged
    delete_branch_on_merge: bool = False
    # block merging if there are outstanding review requests
    block_on_reviews_requested: bool = False
    # comment on merge conflict and remove automerge label
    notify_on_conflict: bool = True
    # don't wait for status checks to run before updating branch
    optimistic_updates: bool = True
    # configuration for commit message of merge
    message: MergeMessage = MergeMessage()
    # status checks that we don't want to wait to complete when they are in a
    # pending state. This is useful for checks that will complete in an
    # indefinite amount of time, like the wip-app checks or status checks
    # requiring manual approval.
    dont_wait_on_status_checks: List[str] = []
    # immediately update a PR whenever the target updates
    update_branch_immediately: bool = False
    # if a PR is passing all checks and is able to be merged, merge it without
    # placing it in the queue. This will introduce some unfairness where those
    # waiting in the queue the longest will not be served first.
    prioritize_ready_to_merge: bool = False
    # never merge a PR. This can be used with merge.update_branch_immediately to
    # automatically update a PR without merging.
    do_not_merge: bool = False


class InvalidVersion(ValueError):
    pass


class V1(BaseModel):
    version: int
    # _internal_ value to require a certain github app ID to process this repo.
    # This is useful for development, so we can globally install the production
    # kodiak, but also run the development version on a specific repo. By
    # setting _app_id to the development github app ID, we can prevent the
    # production kodiak instance from interfering.
    app_id: Optional[str]
    merge: Merge = Merge()

    @validator("version", pre=True, always=True)
    def correct_version(cls, v: int) -> int:
        if v != 1:
            raise InvalidVersion("Version must be `1`")
        return v

    @classmethod
    def parse_toml(
        cls, content: str
    ) -> Union[V1, toml.TomlDecodeError, ValidationError]:
        try:
            return cls.parse_obj(cast(dict, toml.loads(content)))
        except (toml.TomlDecodeError, ValidationError) as e:
            return e
