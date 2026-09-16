"""Assembles a compact text snapshot of the user's current app data for
the chat assistant — projects, open tasks, recent meetings (with their
approved summary, if any), and recent decisions.

Deliberately plain SQL/repository reads, not semantic search: hybrid
retrieval (plan §6) isn't built yet, so this is "recent + open" rather
than "relevant to this question" — good enough for a small personal
workspace, and the honest scope to ship before real retrieval exists.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from odp.models import ProjectStatus, TaskStatus
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.tasks import TasksRepository

MAX_TASKS = 30
MAX_MEETINGS = 10
MAX_DECISIONS = 15


def _due_label(due_utc: str | None) -> str:
    return due_utc if due_utc else "belirtilmemiş"


def _latest_approved_summary(conn: sqlite3.Connection, meeting_id: str) -> str | None:
    row = conn.execute(
        "SELECT payload_json, resolved_payload_json FROM proposals "
        "WHERE source_meeting_id = ? AND kind = 'summary' AND status IN ('approved', 'edited') "
        "ORDER BY created_at DESC LIMIT 1",
        (meeting_id,),
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row["resolved_payload_json"] or row["payload_json"])
    return str(payload.get("summary", ""))


def _recent_decisions(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT p.payload_json, p.resolved_payload_json, m.title AS meeting_title "
        "FROM proposals p LEFT JOIN meetings m ON m.id = p.source_meeting_id "
        "WHERE p.kind = 'decision' AND p.status IN ('approved', 'edited') "
        "ORDER BY p.created_at DESC LIMIT ?",
        (MAX_DECISIONS,),
    ).fetchall()
    result = []
    for row in rows:
        payload = json.loads(row["resolved_payload_json"] or row["payload_json"])
        meeting_title = row["meeting_title"] or "bilinmeyen toplantı"
        result.append((str(payload.get("summary", "")), meeting_title))
    return result


def build_context(conn: sqlite3.Connection, *, timezone: str = "UTC") -> str:
    now_local = datetime.now(ZoneInfo(timezone))
    lines: list[str] = [f"Bugünün tarihi: {now_local.strftime('%Y-%m-%d, %A')} ({timezone})", ""]

    projects = ProjectsRepository(conn).list(status=ProjectStatus.active)
    lines.append(f"## Aktif projeler ({len(projects)})")
    if projects:
        for p in projects:
            lines.append(f"- {p.name}" + (f" — {p.description}" if p.description else ""))
    else:
        lines.append("(yok)")
    lines.append("")

    all_tasks = TasksRepository(conn).list_all()
    open_tasks = [t for t in all_tasks if t.status != TaskStatus.done]
    open_tasks.sort(key=lambda t: t.due_utc or "9999")
    shown_tasks = open_tasks[:MAX_TASKS]
    lines.append(f"## Açık görevler ({len(open_tasks)} toplam, {len(shown_tasks)} gösteriliyor)")
    if shown_tasks:
        for t in shown_tasks:
            owner = t.owner or "atanmamış"
            due = _due_label(t.due_utc)
            lines.append(f"- [{t.status.value}] {t.title} — sorumlu: {owner}, son tarih: {due}")
    else:
        lines.append("(yok)")
    lines.append("")

    meetings = MeetingsRepository(conn).list_all()
    meetings_sorted = sorted(meetings, key=lambda m: m.start_utc, reverse=True)[:MAX_MEETINGS]
    lines.append(f"## Son toplantılar ({len(meetings_sorted)} gösteriliyor)")
    if meetings_sorted:
        for m in meetings_sorted:
            summary = _latest_approved_summary(conn, m.id)
            suffix = f": {summary}" if summary else " — özet yok"
            lines.append(f"- {m.title} ({m.start_utc[:10]})" + suffix)
    else:
        lines.append("(yok)")
    lines.append("")

    decisions = _recent_decisions(conn)
    lines.append(f"## Son kararlar ({len(decisions)} gösteriliyor)")
    if decisions:
        for summary, meeting_title in decisions:
            lines.append(f"- {summary} ({meeting_title})")
    else:
        lines.append("(yok)")

    return "\n".join(lines)
