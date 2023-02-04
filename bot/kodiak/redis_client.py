import redis.asyncio as redis

import kodiak.app_config as conf


def create_connection() -> "redis.Redis[bytes]":
    redis_db = 0
    try:
        redis_db = int(conf.REDIS_URL.database)
    except ValueError:
        pass

    return redis.Redis(
        host=conf.REDIS_URL.hostname or "localhost",
        port=conf.REDIS_URL.port or 6379,
        password=conf.REDIS_URL.password,
        ssl=conf.REDIS_URL.scheme == "rediss",
        db=redis_db,
        socket_keepalive=True,
        socket_timeout=conf.REDIS_SOCKET_TIMEOUT_SEC,
        socket_connect_timeout=conf.REDIS_SOCKET_CONNECT_TIMEOUT_SEC,
        health_check_interval=True,
    )


redis_bot = create_connection()
redis_web_api = create_connection()
