import logging
import signal
import sys
from typing import Any

logger = logging.getLogger(__name__)


class GracefulTermination:
    """
    Wait for inner scope to complete before exiting after receiving SIGINT or SIGTERM.

    source: https://stackoverflow.com/a/50174144
    """

    killed = False
    old_sigint: Any = None
    old_sigterm: Any = None

    def _handler(self, signum: int, frame: object) -> None:
        logging.info("Received %s. Exiting gracefully.", signal.Signals(signum))
        self.killed = True

    def __enter__(self) -> None:
        self.old_sigint = signal.signal(signal.SIGINT, self._handler)
        self.old_sigterm = signal.signal(signal.SIGTERM, self._handler)

    def __exit__(self, type: object, value: object, traceback: object) -> None:
        if self.killed:
            sys.exit(0)
        signal.signal(signal.SIGINT, self.old_sigint)
        signal.signal(signal.SIGTERM, self.old_sigterm)
