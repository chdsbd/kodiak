from typing import Any, Optional

import pytest

from kodiak import app_config as conf
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


def redis_running() -> bool:
    """
    Check if service is listening at the REDIS host and port.
    """
    import socket

    s = socket.socket()
    host = conf.REDIS_URL.hostname
    port = conf.REDIS_URL.port
    assert host and port
    try:
        s.connect((host, port))
        s.close()
        return True
    except ConnectionRefusedError:
        return False


requires_redis = pytest.mark.skipif(not redis_running(), reason="redis is not running")
