"""Helpers that the tests share."""

import asyncio
from collections.abc import Callable

# One limit for each wait of a test: a wait ends at its first success
TIMEOUT = 2.0


async def wait_until(condition: Callable[[], bool]) -> None:
    """Wait until the condition is true, or fail after the limit."""
    async with asyncio.timeout(TIMEOUT):
        while not condition():
            await asyncio.sleep(0.01)
