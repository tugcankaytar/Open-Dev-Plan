"""The GPU semaphore must serialize access — this is the test that would
have caught the plan's missing-GPU-coordination gap (plan §4)."""

from __future__ import annotations

import asyncio

from odp.jobs.gpu_lock import gpu_slot, init_gpu_lock


async def test_gpu_slot_serializes_concurrent_work():
    init_gpu_lock(1)
    concurrent_count = 0
    max_observed = 0

    async def hold_slot() -> None:
        nonlocal concurrent_count, max_observed
        async with gpu_slot():
            concurrent_count += 1
            max_observed = max(max_observed, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1

    await asyncio.gather(*(hold_slot() for _ in range(5)))
    assert max_observed == 1
