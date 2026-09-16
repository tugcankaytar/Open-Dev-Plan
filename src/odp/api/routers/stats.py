from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from odp.api.deps import get_db
from odp.api.schemas import DashboardStats
from odp.repositories.stats import StatsRepository

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(conn: sqlite3.Connection = Depends(get_db)) -> DashboardStats:
    repo = StatsRepository(conn)
    counts = repo.dashboard_counts()
    return DashboardStats(
        **counts,
        task_status_counts=repo.task_status_counts(),
        weekly_activity=repo.weekly_activity(),
    )
