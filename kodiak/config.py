from __future__ import annotations

import typing
from enum import Enum

import toml
from pydantic import BaseModel, validator


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


class Merge(BaseModel):
    # required labels to enable merging of pull request. An empty list indicates
    # no label is required to enable automerge. This is not recommended.
    whitelist: typing.List[str] = ["automerge"]
    # labels to block merging of pull request
    blacklist: typing.List[str] = []
    # action to take when attempting to merge PR. An error will occur if method
    # is disabled for repository
    method: MergeMethod = MergeMethod.merge
    # delete branch when PR is merged
    delete_branch_on_merge: bool = False
    # block merging if there are outstanding review requests
    block_on_reviews_requested: bool = False
    # configuration for commit message of merge
    message: MergeMessage = MergeMessage()


class InvalidVersion(ValueError):
    pass


class V1(BaseModel):
    version: int
    # _internal_ value to require a certain github app ID to process this repo.
    # This is useful for development, so we can globally install the production
    # kodiak, but also run the development version on a specific repo. By
    # setting _app_id to the development github app ID, we can prevent the
    # production kodiak instance from interfering.
    app_id: typing.Optional[str]
    merge: Merge = Merge()

    @validator("version", pre=True, always=True)
    def correct_version(cls, v: int) -> int:
        if v != 1:
            raise InvalidVersion("Version must be `1`")
        return v

    @classmethod
    def parse_toml(cls, content: str) -> V1:
        return cls.parse_obj(typing.cast(dict, toml.loads(content)))
