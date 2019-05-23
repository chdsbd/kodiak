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


class MergeMessage(BaseModel):
    """
    https://developer.github.com/v3/pulls/#merge-a-pull-request-merge-button
    """

    title: MergeTitleStyle = MergeTitleStyle.github_default
    body: MergeBodyStyle = MergeBodyStyle.github_default
    include_pr_number: bool = True


class Merge(BaseModel):
    # required labels to enable merging of pull request. An empty list indicates
    # no label is required to enable automerge. This is not recommended.
    whitelist: typing.List[str] = ["automerge"]
    # labels to block merging of pull request
    blacklist: typing.List[str] = []
    # action to take when attempting to merge PR. An error will occur if method
    # is disabled for repository
    method: MergeMethod = MergeMethod.merge

    delete_branch_on_merge: bool = False
    # configuration for commit message of merge
    message: MergeMessage = MergeMessage()

class InvalidVersion(ValueError):
    pass


class V1(BaseModel):
    version: int
    merge: Merge = Merge()
    block_on_reviews_requested: bool = False

    @validator("version", pre=True, always=True)
    def correct_version(cls, v: int) -> int:
        if v != 1:
            raise InvalidVersion("Version must be `1`")
        return v

    @classmethod
    def parse_toml(cls, content: str) -> V1:
        return cls.parse_obj(typing.cast(dict, toml.loads(content)))
