from typing import Any, Dict, List, Optional

import pydantic
import structlog

logger = structlog.get_logger()


class CommitConnection(pydantic.BaseModel):
    totalCount: int


class User(pydantic.BaseModel):
    databaseId: Optional[int]
    login: str
    name: Optional[str]
    type: str

    def __hash__(self) -> int:
        # defining a hash method allows us to deduplicate CommitAuthors easily.
        return hash(self.databaseId) + hash(self.login) + hash(self.name)


class GitActor(pydantic.BaseModel):
    user: Optional[User]


class Commit(pydantic.BaseModel):
    parents: CommitConnection
    author: Optional[GitActor]


class PullRequestCommit(pydantic.BaseModel):
    commit: Commit


class PullRequestCommitConnection(pydantic.BaseModel):
    nodes: Optional[List[PullRequestCommit]]


class PullRequest(pydantic.BaseModel):
    commitHistory: PullRequestCommitConnection


def get_commits(*, pr: Dict[str, Any]) -> List[Commit]:
    """
    Extract the commit authors from the pull request commits.
    """
    # we use a dict as an ordered set.
    try:
        pull_request = PullRequest.parse_obj(pr)
    except pydantic.ValidationError:
        logger.exception("problem parsing commit authors")
        return []
    nodes = pull_request.commitHistory.nodes
    if not nodes:
        return []
    return [node.commit for node in nodes]
