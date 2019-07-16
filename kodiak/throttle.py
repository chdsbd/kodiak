from collections import defaultdict
from typing import Mapping

from asyncio_throttle import Throttler

# installation_id => Throttler
THROTTLER_CACHE: Mapping[str, Throttler] = defaultdict(
    # TODO(chdsbd): Store rate limits in redis and update via http rate limit response headers
    lambda: Throttler(rate_limit=5000 / 60 / 60)
)


async def get_thottler_for_installation(*, installation_id: str) -> Throttler:
    return THROTTLER_CACHE[installation_id]
