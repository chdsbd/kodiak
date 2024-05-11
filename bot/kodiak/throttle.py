import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, MutableMapping

from typing_extensions import Deque

from kodiak.redis_client import redis_bot


class Throttler:
    """
    via https://github.com/hallazzang/asyncio-throttle

    The MIT License (MIT)

    Copyright (c) 2017-2019 Hanjun Kim

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    def __init__(
        self, rate_limit: float, period: float = 1.0, retry_interval: float = 0.01
    ) -> None:
        self.rate_limit = rate_limit
        self.period = period
        self.retry_interval = retry_interval

        self._task_logs: Deque[float] = deque()

    def flush(self) -> None:
        now = time.time()
        while self._task_logs:
            if now - self._task_logs[0] > self.period:
                self._task_logs.popleft()
            else:
                break

    async def acquire(self) -> None:
        while True:
            self.flush()
            if len(self._task_logs) < self.rate_limit:
                break
            await asyncio.sleep(self.retry_interval)

        self._task_logs.append(time.time())

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass


DEFAULT_REQUESTS_PER_HOUR = 5000
CACHE_TTL_SECS = 60


@dataclass(frozen=True)
class ThrottleEntry:
    throttler: Throttler
    insertion_time: float = field(default_factory=time.monotonic)

    def expired(self) -> bool:
        return (time.monotonic() - self.insertion_time) > CACHE_TTL_SECS


class ThrottleCache:

    _cache: MutableMapping[str, ThrottleEntry]

    def __init__(self) -> None:
        self._cache = {}

    async def get(self, *, installation_id: str) -> Throttler:
        cache_entry = self._cache.get(installation_id)
        if cache_entry and not cache_entry.expired():
            return cache_entry.throttler
        try:
            requests_per_hour_str = await redis_bot.get(
                "installation_rate_limit:" + installation_id
            )
            installation_rate_limit = int(
                requests_per_hour_str or DEFAULT_REQUESTS_PER_HOUR
            )
        except ValueError:
            installation_rate_limit = DEFAULT_REQUESTS_PER_HOUR
        self._cache[installation_id] = ThrottleEntry(
            throttler=Throttler(rate_limit=installation_rate_limit / 60 / 60)
        )
        return self._cache[installation_id].throttler


throttle_cache = ThrottleCache()


async def get_thottler_for_installation(*, installation_id: str) -> Throttler:
    return await throttle_cache.get(installation_id=installation_id)
