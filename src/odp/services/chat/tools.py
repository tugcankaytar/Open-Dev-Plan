"""Tool-calling actions the chat assistant can perform directly.

Scoped deliberately narrow: create/update only, no delete tool — a chat
command is a direct, real-time instruction the user just typed
themselves (unlike the extraction pipeline's inferences from ambiguous
meeting audio, which is why THAT stays proposal-gated per plan §1/#5),
so direct execution is reasonable here. But nothing here is one-way:
every call result is fed back to the model and echoed in its next reply,
so nothing happens silently, and a mistake is a quick manual edit away
(the UI) rather than a deletion to undo.

Dates follow the same rule as everywhere else in this app (plan §1/#1):
the model names a weekday or gives an explicit date, never computes one
itself — resolution happens here, in plain code, reusing the same
resolve_weekday() the scheduler and extraction pipeline use.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from odp.models import Meeting, Task, TaskPriority, TaskStatus
from odp.models.time import to_utc_iso, utc_now_iso
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.tasks import TasksRepository
from odp.services.common.dates import resolve_weekday

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Yeni bir görev oluşturur ve veritabanına kaydeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Görev başlığı"},
                    "owner": {"type": "string", "description": "Sorumlu kişi (opsiyonel)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Öncelik, belirtilmezse 'medium'",
                    },
                    "due_day_of_week": {
                        "type": "string",
                        "description": (
                            "Son tarih bir gün adıysa, İngilizce (örn. 'friday') — tarih HESAPLAMA"
                        ),
                    },
                    "due_explicit_date": {
                        "type": "string",
                        "description": "Son tarih açık bir takvim tarihiyse, YYYY-MM-DD",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Bağlamda verilen proje ID'si (opsiyonel)",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Var olan bir görevin durumunu değiştirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "done"],
                    },
                },
                "required": ["task_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_checklist_item",
            "description": "Var olan bir göreve alt görev/checklist maddesi ekler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    "title": {"type": "string", "description": "Alt görev başlığı"},
                },
                "required": ["task_id", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_meeting",
            "description": "Yeni bir toplantı oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "day_of_week": {
                        "type": "string",
                        "description": "Toplantı günü bir gün adıysa, İngilizce — tarih HESAPLAMA",
                    },
                    "explicit_date": {
                        "type": "string",
                        "description": "Toplantı günü açık bir takvim tarihiyse, YYYY-MM-DD",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Başlangıç saati, HH:MM (24 saat)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Süre, dakika cinsinden — belirtilmezse 60",
                    },
                },
                "required": ["title", "start_time"],
            },
        },
    },
]

_PRIORITY_ALIASES: dict[str, TaskPriority] = {
    "düşük": TaskPriority.low,
    "dusuk": TaskPriority.low,
    "low": TaskPriority.low,
    "orta": TaskPriority.medium,
    "medium": TaskPriority.medium,
    "normal": TaskPriority.medium,
    "yüksek": TaskPriority.high,
    "yuksek": TaskPriority.high,
    "high": TaskPriority.high,
    "acil": TaskPriority.urgent,
    "urgent": TaskPriority.urgent,
    "kritik": TaskPriority.urgent,
}

_STATUS_ALIASES: dict[str, TaskStatus] = {
    "yapılacak": TaskStatus.todo,
    "yapilacak": TaskStatus.todo,
    "todo": TaskStatus.todo,
    "devam ediyor": TaskStatus.in_progress,
    "devam": TaskStatus.in_progress,
    "in_progress": TaskStatus.in_progress,
    "bloke": TaskStatus.blocked,
    "blocked": TaskStatus.blocked,
    "tamamlandı": TaskStatus.done,
    "tamamlandi": TaskStatus.done,
    "done": TaskStatus.done,
    "bitti": TaskStatus.done,
}


def _normalize_priority(value: str | None) -> TaskPriority:
    if not value:
        return TaskPriority.medium
    return _PRIORITY_ALIASES.get(value.strip().lower(), TaskPriority.medium)


def _normalize_status(value: str | None) -> TaskStatus | None:
    if not value:
        return None
    return _STATUS_ALIASES.get(value.strip().lower())


def _resolve_optional_date(
    day_of_week: str | None, explicit_date: str | None, *, timezone: str, end_of_day: bool
) -> str | None:
    if not day_of_week and not explicit_date:
        return None
    tz = ZoneInfo(timezone)
    if explicit_date:
        try:
            target = date.fromisoformat(explicit_date)
        except ValueError:
            return None
    else:
        assert day_of_week is not None
        try:
            target = resolve_weekday(day_of_week, datetime.now(tz).date())
        except ValueError:
            return None
    clock = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return to_utc_iso(datetime.combine(target, clock, tzinfo=tz))


def _tool_create_task(
    conn: sqlite3.Connection, args: dict[str, Any], timezone: str
) -> dict[str, Any]:
    title = str(args.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}
    due_utc = _resolve_optional_date(
        args.get("due_day_of_week"),
        args.get("due_explicit_date"),
        timezone=timezone,
        end_of_day=True,
    )
    now = utc_now_iso()
    task = Task(
        title=title,
        owner=(args.get("owner") or None),
        priority=_normalize_priority(args.get("priority")),
        due_utc=due_utc,
        project_id=(args.get("project_id") or None),
        created_at=now,
        updated_at=now,
    )
    created = TasksRepository(conn).create(task)
    return {
        "task_id": created.id,
        "title": created.title,
        "owner": created.owner,
        "priority": created.priority.value,
        "due_utc": created.due_utc,
        "result": "created",
    }


def _tool_update_task_status(
    conn: sqlite3.Connection, args: dict[str, Any], _timezone: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    status = _normalize_status(args.get("status"))
    if status is None:
        return {"error": f"unrecognized status: {args.get('status')!r}"}
    repo = TasksRepository(conn)
    if repo.get(task_id) is None:
        return {
            "error": f"no task with id {task_id!r} — check the id from the context, don't guess one"
        }
    repo.update_status(task_id, status)
    return {"task_id": task_id, "status": status.value, "result": "updated"}


def _tool_add_checklist_item(
    conn: sqlite3.Connection, args: dict[str, Any], _timezone: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    title = str(args.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}
    repo = TasksRepository(conn)
    if repo.get(task_id) is None:
        return {
            "error": f"no task with id {task_id!r} — check the id from the context, don't guess one"
        }
    item = repo.add_checklist_item(task_id, title)
    return {
        "task_id": task_id,
        "checklist_item_id": item.id,
        "title": item.title,
        "result": "created",
    }


def _tool_create_meeting(
    conn: sqlite3.Connection, args: dict[str, Any], timezone: str
) -> dict[str, Any]:
    title = str(args.get("title") or "").strip()
    start_time = str(args.get("start_time") or "")
    if not title or not start_time:
        return {"error": "title and start_time are required"}
    try:
        hh, mm = (int(p) for p in start_time.split(":"))
    except ValueError:
        return {"error": f"start_time must be HH:MM, got {start_time!r}"}

    tz = ZoneInfo(timezone)
    day_of_week = args.get("day_of_week")
    explicit_date = args.get("explicit_date")
    if explicit_date:
        target = date.fromisoformat(explicit_date)
    elif day_of_week:
        target = resolve_weekday(day_of_week, datetime.now(tz).date())
    else:
        target = datetime.now(tz).date()

    start_dt = datetime.combine(target, time(hh, mm), tzinfo=tz)
    duration = int(args.get("duration_minutes") or 60)
    end_dt = start_dt + timedelta(minutes=duration)

    now = utc_now_iso()
    meeting = Meeting(
        title=title,
        start_utc=to_utc_iso(start_dt),
        end_utc=to_utc_iso(end_dt),
        timezone=timezone,
        created_at=now,
        updated_at=now,
    )
    created = MeetingsRepository(conn).create(meeting)
    return {
        "meeting_id": created.id,
        "title": created.title,
        "start_utc": created.start_utc,
        "end_utc": created.end_utc,
        "result": "created",
    }


_HANDLERS: dict[str, Any] = {
    "create_task": _tool_create_task,
    "update_task_status": _tool_update_task_status,
    "add_checklist_item": _tool_add_checklist_item,
    "create_meeting": _tool_create_meeting,
}


def execute_tool(
    conn: sqlite3.Connection, name: str, arguments: dict[str, Any], *, timezone: str
) -> dict[str, Any]:
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        result: dict[str, Any] = handler(conn, arguments, timezone)
        return result
    except Exception as exc:
        # Any failure is reported back to the model as a tool result (so it
        # can explain to the user), not raised — a bad tool call must not
        # crash the whole chat stream.
        return {"error": str(exc)}
