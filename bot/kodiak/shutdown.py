"""
Stop consuming queues on SIGTERM so `docker stop` doesn't kill us mid-event.

Our processes run as PID 1 in their containers, where the kernel ignores
SIGTERM unless we install a handler.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

logger = structlog.get_logger()

_stop_requested = False


def stop_requested() -> bool:
    return _stop_requested


def request_stop() -> None:
    global _stop_requested
    if not _stop_requested:
        logger.info("shutdown_requested")
    _stop_requested = True


def install_sigterm_handler() -> None:
    """
    Consumer loops check `stop_requested()` before popping their next item, so
    they finish the item in hand and exit.
    """
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, request_stop)
