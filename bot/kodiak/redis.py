from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

import asyncio_redis
import structlog

from kodiak import app_config as conf

conn: asyncio_redis.Connection | None = None

logger = structlog.get_logger()


async def get_conn() -> AsyncIterator[asyncio_redis.Connection]:
    """
    FastAPI compatible function for accessing the connection pool
    see: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield
    """
    global conn
    if conn is None:
        logger.info("creating redis pool...")
        try:
            redis_db = int(conf.REDIS_URL.database)
        except ValueError:
            redis_db = 0
        conn = await asyncio_redis.Pool.create(
            host=conf.REDIS_URL.hostname or "localhost",
            port=conf.REDIS_URL.port or 6379,
            password=conf.REDIS_URL.password or None,
            db=redis_db,
            poolsize=conf.REDIS_POOL_SIZE,
        )
        logger.info("redis pool created.")
    yield conn
