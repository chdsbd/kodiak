from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    async def __aenter__(self) -> None: ...

    async def __aexit__(
        self, exc_type: object, exc_value: object, traceback: object
    ) -> None: ...


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


class RecordingLogger:
    """
    Fake structlog logger that records each log call as a dict.
    """

    def __init__(
        self,
        records: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.records: List[Dict[str, Any]] = [] if records is None else records
        self.context = context or {}

    def bind(self, **kwargs: Any) -> RecordingLogger:
        return RecordingLogger(self.records, {**self.context, **kwargs})

    def _log(self, level: str, event: str, **kwargs: Any) -> None:
        self.records.append(dict(self.context, **kwargs, event=event, level=level))

    def info(self, event: str, **kwargs: Any) -> None:
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log("warning", event, **kwargs)

    def events(self, event: str) -> List[Dict[str, Any]]:
        return [record for record in self.records if record["event"] == event]
