"""Assembles a compact text snapshot of the user's current app data for
the chat assistant — customers, projects, open tasks, recent meetings
(with their approved summary, if any), pending proposals, and recent
decisions. Every listed record carries its `[id: ...]` so a tool call
can reference it precisely instead of the model guessing one.

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

from odp.models import TaskStatus
from odp.repositories.customers import CustomersRepository
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.tasks import TasksRepository

MAX_TASKS = 30
MAX_MEETINGS = 10
MAX_DECISIONS = 15
MAX_PENDING_PROPOSALS = 15


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


def _pending_proposals_summary(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    """Returns (id, kind, one_line_description, meeting_title) for the
    most recent still-pending proposals, across all meetings."""
    rows = conn.execute(
        "SELECT p.id, p.kind, p.payload_json, m.title AS meeting_title "
        "FROM proposals p LEFT JOIN meetings m ON m.id = p.source_meeting_id "
        "WHERE p.status = 'pending' ORDER BY p.created_at DESC LIMIT ?",
        (MAX_PENDING_PROPOSALS,),
    ).fetchall()
    result = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        text = payload.get("title") or payload.get("summary") or ""
        result.append(
            (row["id"], row["kind"], str(text), row["meeting_title"] or "bilinmeyen toplantı")
        )
    return result


def build_context(conn: sqlite3.Connection, *, timezone: str = "UTC") -> str:
    now_local = datetime.now(ZoneInfo(timezone))
    lines: list[str] = [f"Bugünün tarihi: {now_local.strftime('%Y-%m-%d, %A')} ({timezone})", ""]
    lines.append(
        "(Aşağıdaki listelerdeki [id: ...] değerleri gerçek kayıt ID'leridir — bir araç "
        "çağırırken SADECE buradaki ID'leri kullan, asla tahmin etme veya uydurma.)"
    )
    lines.append("")

    customers = CustomersRepository(conn).list()
    lines.append(f"## Müşteriler ({len(customers)})")
    if customers:
        for c in customers:
            lines.append(
                f"- [id: {c.id}] {c.name}" + (f" — {c.description}" if c.description else "")
            )
    else:
        lines.append("(yok)")
    lines.append("")

    projects = ProjectsRepository(conn).list()
    customer_name_by_id = {c.id: c.name for c in customers}
    lines.append(f"## Projeler ({len(projects)})")
    if projects:
        for p in projects:
            customer_label = (
                f", müşteri: {customer_name_by_id.get(p.customer_id)}" if p.customer_id else ""
            )
            lines.append(f"- [id: {p.id}] {p.name} [{p.status.value}]{customer_label}")
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
            tags = f", etiket: {', '.join(t.tags)}" if t.tags else ""
            lines.append(
                f"- [id: {t.id}] [{t.status.value}/{t.priority.value}] {t.title} — "
                f"sorumlu: {owner}, son tarih: {due}{tags}"
            )
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
            lines.append(f"- [id: {m.id}] {m.title} ({m.start_utc[:10]})" + suffix)
    else:
        lines.append("(yok)")
    lines.append("")

    pending = _pending_proposals_summary(conn)
    lines.append(f"## Onay bekleyen öneriler ({len(pending)} gösteriliyor)")
    if pending:
        for pid, kind, text, meeting_title in pending:
            lines.append(f"- [id: {pid}] [{kind}] {text} ({meeting_title})")
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
