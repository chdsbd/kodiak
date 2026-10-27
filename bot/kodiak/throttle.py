import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Mapping, Tuple


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

    def set_hourly_limit(self, requests_per_hour: int) -> None:
        """
        Pace requests to a share of GitHub's hourly limit.

        We use a one minute window so the limit isn't rounded up to a whole
        request per second, while still allowing short bursts.
        """
        self.period = 60
        self.rate_limit = requests_per_hour * RATE_LIMIT_USAGE / 60

    async def __aenter__(self) -> None:
        await self.acquire()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass


# share of GitHub's rate limit we use. We leave headroom for other processes
# using the same installation, like the pull request refresh job.
RATE_LIMIT_USAGE = 0.8

# (installation_id, rate limit resource) => Throttler
#
# GitHub limits REST ("core") and GraphQL ("graphql") requests separately. We
# start at GitHub's minimum limit and update from response headers.
THROTTLER_CACHE: Mapping[Tuple[str, str], Throttler] = defaultdict(
    lambda: Throttler(rate_limit=5000 / 60 / 60)
)


def get_thottler_for_installation(
    *, installation_id: str, resource: str = "core"
) -> Throttler:
    return THROTTLER_CACHE[(installation_id, resource)]


def update_rate_limit(
    *, installation_id: str, resource: str, requests_per_hour: int
) -> None:
    THROTTLER_CACHE[(installation_id, resource)].set_hourly_limit(requests_per_hour)
