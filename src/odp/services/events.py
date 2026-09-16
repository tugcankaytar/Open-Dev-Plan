"""Process-wide "something changed" broadcaster — powers the live-update
SSE stream (`/api/events`) so the frontend never needs a manual refresh.
Any write anywhere — a REST call, a background extraction job finishing,
a chat tool call — publishes here, and every open browser tab is told to
refetch.

Module-level singleton, same pattern as jobs/gpu_lock.py's GPU
semaphore: this is a single-process app, so one broadcaster serves the
whole server. `scope` is currently advisory only (the frontend does a
blanket cache invalidation on any event) but is passed through so a
future, more targeted client doesn't need a wire-format change.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

_subscribers: set[asyncio.Queue[str]] = set()


def publish(scope: str = "*") -> None:
    for q in list(_subscribers):
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(scope)


async def subscribe() -> AsyncIterator[str]:
    """Yield scope strings as they're published, until the caller stops
    iterating (e.g. the client disconnects)."""
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    try:
        while True:
            yield await q.get()
    finally:
        _subscribers.discard(q)
