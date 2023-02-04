import kodiak.app_config as conf
import redis.asyncio as redis


def create_connection() -> 'redis.Redis["bytes"]':
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
    )


main_redis = create_connection()
usage_redis = create_connection()
