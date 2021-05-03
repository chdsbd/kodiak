from typing import Any, Optional

from kodiak.queries import Commit, CommitConnection, GitActor, PullRequestCommitUser


def create_commit(
    *,
    database_id: Optional[int],
    name: Optional[str],
    login: str,
    type: str,
    parents: int = 1,
) -> Commit:
    return Commit(
        parents=CommitConnection(totalCount=parents),
        author=GitActor(
            user=PullRequestCommitUser(
                databaseId=database_id, name=name, login=login, type=type
            )
        ),
    )


class FakeThottler:
    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        ...
