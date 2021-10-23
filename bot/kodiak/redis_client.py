import asyncio_redis

import kodiak.app_config as conf


async def create_connection() -> asyncio_redis.Connection:
    redis_db = 0
    try:
        redis_db = int(conf.REDIS_URL.database)
    except ValueError:
        pass

    return await asyncio_redis.Connection.create(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=(
            conf.REDIS_URL.password.encode() if conf.REDIS_URL.password else None
        ),
        ssl=conf.REDIS_URL.scheme == "rediss",
        db=redis_db,
    )
