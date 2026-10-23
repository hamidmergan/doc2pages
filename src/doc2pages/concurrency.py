"""Several model calls at once, and one at a time as soon as the server struggles.

Nothing is remembered beyond one run: the next run starts at the full number again.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .client import overloaded

logger = logging.getLogger("doc2pages")

# Marks a job that was never started because the run has to stop.
SKIPPED = object()

# One failure of a job is tried again alone, a second one ends the run.
_ATTEMPTS = 2

__all__ = ["SKIPPED", "overloaded", "run_limited"]


async def run_limited(jobs: list[Callable[[], Awaitable[Any]]], at_once: int, *,
                      may_start: Callable[[], bool] | None = None) -> list[Any]:
    """Every job, at most ``at_once`` running, results in the order of the jobs."""
    state = {"limit": max(1, at_once), "running": 0}
    change = asyncio.Condition()

    async def seat() -> None:
        async with change:
            await change.wait_for(lambda: state["running"] < state["limit"])
            state["running"] += 1

    async def leave() -> None:
        async with change:
            state["running"] -= 1
            change.notify_all()

    async def one(job: Callable[[], Awaitable[Any]]) -> Any:
        for attempt in range(1, _ATTEMPTS + 1):
            await seat()
            try:
                if may_start is not None and not may_start():
                    return SKIPPED
                return await job()
            except Exception as e:
                if not overloaded(e) or attempt >= _ATTEMPTS:
                    raise
                if state["limit"] > 1:
                    logger.warning("Server overloaded (%s), from now on one call after the other", e)
                state["limit"] = 1
            finally:
                await leave()
        raise RuntimeError("unreachable")

    return list(await asyncio.gather(*(one(j) for j in jobs)))
