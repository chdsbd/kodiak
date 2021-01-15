from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast

import toml
from pydantic import BaseModel, ValidationError, validator
from typing_extensions import Literal


class MergeMethod(str, Enum):
    merge = "merge"
    squash = "squash"
    rebase = "rebase"
    rebaseff = "rebase-ff"


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
    include_pull_request_author: bool = False
    include_coauthors: bool = False
    include_pull_request_url: bool = False
    cut_body_before: str = ""
    cut_body_after: str = ""


# this pattern indicates that the user has the field unset.
UNSET_TITLE_REGEX = ":::|||kodiak|||internal|||reserved|||:::"
DEFAULT_TITLE_REGEX = "^WIP:.*"


class AutomergeDependencies(BaseModel):
    versions: List[Literal["major", "minor", "patch"]] = []
    usernames: List[str] = []


class Merge(BaseModel):
    # label or labels to enable merging of pull request.
    automerge_label: Union[str, List[str]] = "automerge"
    automerge_dependencies: AutomergeDependencies = AutomergeDependencies()
    # if disabled, kodiak won't require a label to queue a PR for merge
    require_automerge_label: bool = True
    # regex to match against title and block merging. Set to empty string to
    # disable check.
    blacklist_title_regex: str = UNSET_TITLE_REGEX  # deprecated for blocking_title_regex
    blocking_title_regex: str = UNSET_TITLE_REGEX
    # labels to block merging of pull request
    blacklist_labels: List[str] = []  # deprecated for blocking_labels
    blocking_labels: List[str] = []
    # action to take when attempting to merge PR. An error will occur if method
    # is disabled for repository
    method: Optional[MergeMethod] = None
    # delete branch when PR is merged
    delete_branch_on_merge: bool = False
    # DEPRECATED
    # this feature is flawed and cannot be fixed. see
    # https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332.
    #
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
    # DEPRECATED
    # This setting only updates PRs that are passing passing all
    # requirements or waiting for status checks to pass. `update.always = True`
    # will deliver better behavior in many use cases.
    #
    # immediately update a PR whenever the target updates
    update_branch_immediately: bool = False
    # if a PR is passing all checks and is able to be merged, merge it without
    # placing it in the queue. This will introduce some unfairness where those
    # waiting in the queue the longest will not be served first.
    prioritize_ready_to_merge: bool = False
    # when applied to a PR, add the PR to the front of the merge queue.
    priority_merge_label: Optional[str] = None
    # never merge a PR. This can be used with merge.update_branch_immediately to
    # automatically update a PR without merging.
    do_not_merge: bool = False


class Update(BaseModel):
    # update PR whenever the PR is out of date with the base branch. PR will be
    # updated regardless of failing requirements for merge (e.g. failing status
    # checks, missing reviews, blacklist labels). Kodiak will only update the PR
    # if the automerge label is enabled or `update.require_automerge_label` is
    # false.
    always: bool = False
    require_automerge_label: bool = True
    autoupdate_label: Optional[str] = None
    # Do not update PRs created by a listed user.
    blacklist_usernames: List[str] = []  # deprecated for ignored_usernames
    ignored_usernames: List[str] = []


class Approve(BaseModel):
    # auto approve any PR created by a listed user.
    auto_approve_usernames: List[str] = []


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
    update: Update = Update()
    approve: Approve = Approve()
    # when added to a Pull Request Kodiak will be prevented from taking any action
    # (approvals, updates, merges, comments, labels). Kodiak will still set
    # status checks. A user should generally not need to change this label as it
    # should rarely be applied.
    disable_bot_label: str = "kodiak:disabled"

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
            return cls.parse_obj(cast(Dict[str, Any], toml.loads(content)))
        except (toml.TomlDecodeError, ValidationError) as e:
            return e
