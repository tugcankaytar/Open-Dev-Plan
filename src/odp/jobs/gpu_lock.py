"""Process-wide GPU semaphore.

A 16GB-class card cannot hold the extraction LLM (~14GB), the prose LLM
(~9GB) and Whisper (~3GB) at once. Every GPU-bound job — LLM generation,
transcription, LoRA training — must acquire this lock before touching the
model and release it (unloading via `keep_alive=0` where applicable)
before the next job runs. Skipping this is how you get a CUDA OOM crash
on the first real meeting (plan §4).

`gpu_concurrency` defaults to 1; it's a Settings field only so a future
multi-GPU box can raise it without a code change.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

_lock: asyncio.Semaphore | None = None


def init_gpu_lock(concurrency: int = 1) -> None:
    global _lock
    _lock = asyncio.Semaphore(concurrency)


def _get_lock() -> asyncio.Semaphore:
    if _lock is None:
        # Lazy default so tests / scripts that never call init_gpu_lock()
        # still work with the safe single-slot default.
        init_gpu_lock(1)
    assert _lock is not None
    return _lock


@asynccontextmanager
async def gpu_slot() -> AsyncIterator[None]:
    """Hold the single GPU slot for the duration of the `async with` block."""
    lock = _get_lock()
    async with lock:
        yield
