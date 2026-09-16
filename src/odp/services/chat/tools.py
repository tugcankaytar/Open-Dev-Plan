"""Tool-calling actions the chat assistant can perform directly — full
parity with what the UI itself can do: create/update/delete on
customers, projects, tasks (+ checklist), meetings, and resolving
proposals.

A chat command is a direct, real-time instruction the user just typed
themselves (unlike the extraction pipeline's inferences from ambiguous
meeting audio, which is why THAT stays proposal-gated per plan §1/#5),
so direct execution is reasonable here. Every call result is fed back
to the model and echoed in its next reply, so nothing happens silently.

Delete tools carry a required `confirmed` argument and refuse to run
without it — see chat_assistant.md for the paired prompt rule (ask the
user, wait for an explicit yes, only then call again with
confirmed=true). That's the real backstop; the schema requirement just
makes an accidental first-try delete return an error instead of a
result.

Every successful write publishes a live-update event (services/events)
so every open browser tab refreshes without a manual reload — the same
signal the REST endpoints emit, since a chat command bypasses them.

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

from odp.models import (
    ChecklistItem,
    Meeting,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
)
from odp.models.time import to_utc_iso, utc_now_iso
from odp.repositories.customers import CustomersRepository
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.tasks import TasksRepository
from odp.services import events
from odp.services.common.dates import resolve_weekday
from odp.services.proposals import resolve_proposal
from odp.services.proposals.resolve import ProposalResolutionError

_CONFIRM_FIELD = {
    "confirmed": {
        "type": "boolean",
        "description": (
            "MUTLAKA true olmalı — SADECE kullanıcı sohbette açıkça onay verdikten sonra "
            "true gönder. Kullanıcı henüz onay vermediyse bu aracı ÇAĞIRMA, önce sor."
        ),
    }
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    # --- customers ---
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "Yeni bir müşteri kaydı oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Müşteri adı"},
                    "description": {"type": "string", "description": "Açıklama (opsiyonel)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer",
            "description": "Var olan bir müşterinin adını/açıklamasını günceller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Bağlamda verilen müşteri ID'si",
                    },
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_customer",
            "description": (
                "Bir müşteriyi KALICI olarak siler (bağlı projeler müşterisiz kalır). "
                "Geri alınamaz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Bağlamda verilen müşteri ID'si",
                    },
                    **_CONFIRM_FIELD,
                },
                "required": ["customer_id", "confirmed"],
            },
        },
    },
    # --- projects ---
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Yeni bir proje oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "customer_id": {
                        "type": "string",
                        "description": (
                            "Bağlamda verilen müşteri ID'si (opsiyonel, dahili proje ise boş bırak)"
                        ),
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_project",
            "description": (
                "Var olan bir projenin adını, açıklamasını, durumunu veya bağlı "
                "müşterisini günceller."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Bağlamda verilen proje ID'si"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["active", "paused", "done", "archived"],
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "Yeni müşteri ID'si; müşteriyi kaldırmak için 'yok' yaz",
                    },
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_project",
            "description": (
                "Bir projeyi KALICI olarak siler (bağlı görevler projesiz kalır). Geri alınamaz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Bağlamda verilen proje ID'si"},
                    **_CONFIRM_FIELD,
                },
                "required": ["project_id", "confirmed"],
            },
        },
    },
    # --- tasks ---
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Yeni bir görev oluşturur ve veritabanına kaydeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Görev başlığı"},
                    "description": {"type": "string", "description": "Açıklama (opsiyonel)"},
                    "owner": {"type": "string", "description": "Sorumlu kişi (opsiyonel)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Öncelik, belirtilmezse 'medium'",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Etiketler (opsiyonel)",
                    },
                    "due_day_of_week": {
                        "type": "string",
                        "description": "Son tarih bir gün adıysa, İngilizce — tarih HESAPLAMA",
                    },
                    "due_explicit_date": {"type": "string", "description": "Son tarih YYYY-MM-DD"},
                    "start_day_of_week": {
                        "type": "string",
                        "description": (
                            "Başlangıç tarihi bir gün adıysa, İngilizce — tarih HESAPLAMA"
                        ),
                    },
                    "start_explicit_date": {
                        "type": "string",
                        "description": "Başlangıç YYYY-MM-DD",
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
            "name": "update_task",
            "description": "Var olan bir görevin herhangi bir alanını günceller (durum dahil).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "owner": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "done"],
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Verilirse TÜM etiket listesinin yerini alır",
                    },
                    "due_day_of_week": {"type": "string", "description": "İngilizce gün adı"},
                    "due_explicit_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "start_day_of_week": {"type": "string", "description": "İngilizce gün adı"},
                    "start_explicit_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "project_id": {"type": "string", "description": "Yeni proje ID'si"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Bir görevi KALICI olarak siler. Geri alınamaz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    **_CONFIRM_FIELD,
                },
                "required": ["task_id", "confirmed"],
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
            "name": "toggle_checklist_item",
            "description": "Bir görevin alt görevini tamamlandı/tamamlanmadı olarak işaretler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    "item_title": {
                        "type": "string",
                        "description": "Alt görevin başlığı (tam veya kısmi eşleşme yeterli)",
                    },
                    "done": {"type": "boolean"},
                },
                "required": ["task_id", "item_title", "done"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_checklist_item",
            "description": "Bir görevden alt görev maddesini kaldırır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Bağlamda verilen görev ID'si"},
                    "item_title": {
                        "type": "string",
                        "description": "Kaldırılacak alt görevin başlığı",
                    },
                },
                "required": ["task_id", "item_title"],
            },
        },
    },
    # --- meetings ---
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
                    "explicit_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "start_time": {
                        "type": "string",
                        "description": "Başlangıç saati, HH:MM (24 saat)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Süre, dakika — belirtilmezse 60",
                    },
                },
                "required": ["title", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_meeting",
            "description": (
                "Bir toplantıyı ve tüm transkript/önerilerini KALICI olarak siler. Geri alınamaz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {
                        "type": "string",
                        "description": "Bağlamda verilen toplantı ID'si",
                    },
                    **_CONFIRM_FIELD,
                },
                "required": ["meeting_id", "confirmed"],
            },
        },
    },
    # --- proposals ---
    {
        "type": "function",
        "function": {
            "name": "resolve_proposal",
            "description": "Bekleyen bir öneriyi (görev/karar/özet) onaylar veya reddeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                        "description": "Bağlamda verilen öneri ID'si",
                    },
                    "action": {"type": "string", "enum": ["approve", "reject"]},
                },
                "required": ["proposal_id", "action"],
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

_PROJECT_STATUS_ALIASES: dict[str, ProjectStatus] = {
    "aktif": ProjectStatus.active,
    "active": ProjectStatus.active,
    "duraklatıldı": ProjectStatus.paused,
    "duraklatildi": ProjectStatus.paused,
    "paused": ProjectStatus.paused,
    "tamamlandı": ProjectStatus.done,
    "tamamlandi": ProjectStatus.done,
    "done": ProjectStatus.done,
    "arşivlendi": ProjectStatus.archived,
    "arsivlendi": ProjectStatus.archived,
    "archived": ProjectStatus.archived,
}

_NONE_WORDS = {"", "yok", "none", "null", "hiçbiri", "hicbiri", "müşteri yok", "musteri yok"}


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    return None if value.strip().lower() in _NONE_WORDS else value


def _normalize_priority(value: str | None) -> TaskPriority:
    if not value:
        return TaskPriority.medium
    return _PRIORITY_ALIASES.get(value.strip().lower(), TaskPriority.medium)


def _normalize_status(value: str | None) -> TaskStatus | None:
    if not value:
        return None
    return _STATUS_ALIASES.get(value.strip().lower())


def _normalize_project_status(value: str | None) -> ProjectStatus | None:
    if not value:
        return None
    return _PROJECT_STATUS_ALIASES.get(value.strip().lower())


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


def _require_confirmation(args: dict[str, Any]) -> dict[str, Any] | None:
    if args.get("confirmed") is not True:
        return {
            "error": (
                "confirmation required: this is a permanent delete — ask the user to "
                "explicitly confirm first, then call this tool again with confirmed=true"
            )
        }
    return None


def _find_checklist_item(
    conn: sqlite3.Connection, task_id: str, title_query: str
) -> ChecklistItem | dict[str, Any]:
    items = TasksRepository(conn).list_checklist_items(task_id)
    query = title_query.strip().lower()
    matches = [i for i in items if query in i.title.lower()]
    if not matches:
        return {"error": f"no checklist item matching {title_query!r} found on this task"}
    if len(matches) > 1:
        titles = [i.title for i in matches]
        return {
            "error": f"multiple checklist items match {title_query!r}: {titles} — be more specific"
        }
    return matches[0]


# =============================================================== customers


async def _tool_create_customer(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}
    customer = CustomersRepository(conn).create(name, str(args.get("description") or ""))
    events.publish("customers")
    return {"customer_id": customer.id, "name": customer.name, "result": "created"}


async def _tool_update_customer(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    customer_id = str(args.get("customer_id") or "")
    repo = CustomersRepository(conn)
    if repo.get(customer_id) is None:
        return {"error": f"no customer with id {customer_id!r} — use the id from the context"}
    updated = repo.update(
        customer_id, name=args.get("name") or None, description=args.get("description")
    )
    events.publish("customers")
    assert updated is not None
    return {"customer_id": updated.id, "name": updated.name, "result": "updated"}


async def _tool_delete_customer(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    if (err := _require_confirmation(args)) is not None:
        return err
    customer_id = str(args.get("customer_id") or "")
    repo = CustomersRepository(conn)
    if repo.get(customer_id) is None:
        return {"error": f"no customer with id {customer_id!r} — use the id from the context"}
    repo.delete(customer_id)
    events.publish("customers")
    events.publish("projects")  # linked projects lose their customer_id
    return {"customer_id": customer_id, "result": "deleted"}


# ================================================================ projects


async def _tool_create_project(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}
    project = ProjectsRepository(conn).create(
        name, str(args.get("description") or ""), _none_if_empty(args.get("customer_id"))
    )
    events.publish("projects")
    return {"project_id": project.id, "name": project.name, "result": "created"}


async def _tool_update_project(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    project_id = str(args.get("project_id") or "")
    repo = ProjectsRepository(conn)
    if repo.get(project_id) is None:
        return {"error": f"no project with id {project_id!r} — use the id from the context"}

    kwargs: dict[str, Any] = {}
    if args.get("name"):
        kwargs["name"] = args["name"]
    if args.get("description") is not None:
        kwargs["description"] = args["description"]
    if args.get("status"):
        status = _normalize_project_status(args["status"])
        if status is None:
            return {"error": f"unrecognized status: {args.get('status')!r}"}
        kwargs["status"] = status
    if "customer_id" in args:
        kwargs["customer_id"] = _none_if_empty(args.get("customer_id"))

    updated = repo.update(project_id, **kwargs)
    events.publish("projects")
    assert updated is not None
    return {
        "project_id": updated.id,
        "name": updated.name,
        "status": updated.status.value,
        "result": "updated",
    }


async def _tool_delete_project(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    if (err := _require_confirmation(args)) is not None:
        return err
    project_id = str(args.get("project_id") or "")
    repo = ProjectsRepository(conn)
    if repo.get(project_id) is None:
        return {"error": f"no project with id {project_id!r} — use the id from the context"}
    repo.delete(project_id)
    events.publish("projects")
    events.publish("tasks")  # linked tasks lose their project_id
    return {"project_id": project_id, "result": "deleted"}


# =================================================================== tasks


async def _tool_create_task(
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
    start_utc = _resolve_optional_date(
        args.get("start_day_of_week"),
        args.get("start_explicit_date"),
        timezone=timezone,
        end_of_day=False,
    )
    now = utc_now_iso()
    task = Task(
        title=title,
        description=str(args.get("description") or ""),
        owner=(args.get("owner") or None),
        priority=_normalize_priority(args.get("priority")),
        tags=list(args.get("tags") or []),
        due_utc=due_utc,
        start_utc=start_utc,
        project_id=(args.get("project_id") or None),
        created_at=now,
        updated_at=now,
    )
    created = TasksRepository(conn).create(task)
    events.publish("tasks")
    return {
        "task_id": created.id,
        "title": created.title,
        "owner": created.owner,
        "priority": created.priority.value,
        "due_utc": created.due_utc,
        "start_utc": created.start_utc,
        "result": "created",
    }


async def _tool_update_task(
    conn: sqlite3.Connection, args: dict[str, Any], timezone: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    repo = TasksRepository(conn)
    if repo.get(task_id) is None:
        return {
            "error": f"no task with id {task_id!r} — use the id from the context, don't guess one"
        }

    kwargs: dict[str, Any] = {}
    if args.get("title"):
        kwargs["title"] = args["title"]
    if args.get("description") is not None:
        kwargs["description"] = args["description"]
    if "owner" in args:
        kwargs["owner"] = args.get("owner") or None
    if args.get("priority"):
        kwargs["priority"] = _normalize_priority(args["priority"])
    if args.get("status"):
        status = _normalize_status(args["status"])
        if status is None:
            return {"error": f"unrecognized status: {args.get('status')!r}"}
        kwargs["status"] = status
    if "tags" in args:
        kwargs["tags"] = list(args.get("tags") or [])
    if args.get("due_day_of_week") or args.get("due_explicit_date"):
        kwargs["due_utc"] = _resolve_optional_date(
            args.get("due_day_of_week"),
            args.get("due_explicit_date"),
            timezone=timezone,
            end_of_day=True,
        )
    if args.get("start_day_of_week") or args.get("start_explicit_date"):
        kwargs["start_utc"] = _resolve_optional_date(
            args.get("start_day_of_week"),
            args.get("start_explicit_date"),
            timezone=timezone,
            end_of_day=False,
        )
    if args.get("project_id"):
        kwargs["project_id"] = _none_if_empty(args.get("project_id"))

    updated = repo.update(task_id, **kwargs)
    events.publish("tasks")
    assert updated is not None
    return {
        "task_id": updated.id,
        "title": updated.title,
        "status": updated.status.value,
        "result": "updated",
    }


async def _tool_delete_task(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    if (err := _require_confirmation(args)) is not None:
        return err
    task_id = str(args.get("task_id") or "")
    repo = TasksRepository(conn)
    if repo.get(task_id) is None:
        return {
            "error": f"no task with id {task_id!r} — use the id from the context, don't guess one"
        }
    repo.delete(task_id)
    events.publish("tasks")
    return {"task_id": task_id, "result": "deleted"}


async def _tool_add_checklist_item(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    title = str(args.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}
    repo = TasksRepository(conn)
    if repo.get(task_id) is None:
        return {
            "error": f"no task with id {task_id!r} — use the id from the context, don't guess one"
        }
    item = repo.add_checklist_item(task_id, title)
    events.publish("tasks")
    return {
        "task_id": task_id,
        "checklist_item_id": item.id,
        "title": item.title,
        "result": "created",
    }


async def _tool_toggle_checklist_item(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    item_title = str(args.get("item_title") or "")
    found = _find_checklist_item(conn, task_id, item_title)
    if isinstance(found, dict):
        return found
    done = bool(args.get("done"))
    TasksRepository(conn).set_checklist_item_done(found.id, done)
    events.publish("tasks")
    return {
        "task_id": task_id,
        "checklist_item_id": found.id,
        "title": found.title,
        "done": done,
        "result": "updated",
    }


async def _tool_delete_checklist_item(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "")
    item_title = str(args.get("item_title") or "")
    found = _find_checklist_item(conn, task_id, item_title)
    if isinstance(found, dict):
        return found
    TasksRepository(conn).delete_checklist_item(found.id)
    events.publish("tasks")
    return {"task_id": task_id, "title": found.title, "result": "deleted"}


# ================================================================ meetings


async def _tool_create_meeting(
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
    events.publish("meetings")
    return {
        "meeting_id": created.id,
        "title": created.title,
        "start_utc": created.start_utc,
        "end_utc": created.end_utc,
        "result": "created",
    }


async def _tool_delete_meeting(
    conn: sqlite3.Connection, args: dict[str, Any], _tz: str
) -> dict[str, Any]:
    if (err := _require_confirmation(args)) is not None:
        return err
    meeting_id = str(args.get("meeting_id") or "")
    repo = MeetingsRepository(conn)
    if repo.get(meeting_id) is None:
        return {"error": f"no meeting with id {meeting_id!r} — use the id from the context"}
    repo.delete(meeting_id)
    events.publish("meetings")
    events.publish("proposals")  # its proposals cascade-deleted with it
    return {"meeting_id": meeting_id, "result": "deleted"}


# =============================================================== proposals


async def _tool_resolve_proposal(
    conn: sqlite3.Connection, args: dict[str, Any], timezone: str
) -> dict[str, Any]:
    proposal_id = str(args.get("proposal_id") or "")
    action = args.get("action")
    if action not in ("approve", "reject"):
        return {"error": f"action must be 'approve' or 'reject', got {action!r}"}
    try:
        resolved = await resolve_proposal(
            conn, proposal_id=proposal_id, action=action, default_timezone=timezone
        )
    except ProposalResolutionError as exc:
        return {"error": str(exc)}
    events.publish("proposals")
    if resolved.resolved_task_id:
        events.publish("tasks")
    return {
        "proposal_id": resolved.id,
        "status": resolved.status.value,
        "resolved_task_id": resolved.resolved_task_id,
        "result": "resolved",
    }


_HANDLERS: dict[str, Any] = {
    "create_customer": _tool_create_customer,
    "update_customer": _tool_update_customer,
    "delete_customer": _tool_delete_customer,
    "create_project": _tool_create_project,
    "update_project": _tool_update_project,
    "delete_project": _tool_delete_project,
    "create_task": _tool_create_task,
    "update_task": _tool_update_task,
    "delete_task": _tool_delete_task,
    "add_checklist_item": _tool_add_checklist_item,
    "toggle_checklist_item": _tool_toggle_checklist_item,
    "delete_checklist_item": _tool_delete_checklist_item,
    "create_meeting": _tool_create_meeting,
    "delete_meeting": _tool_delete_meeting,
    "resolve_proposal": _tool_resolve_proposal,
}


async def execute_tool(
    conn: sqlite3.Connection, name: str, arguments: dict[str, Any], *, timezone: str
) -> dict[str, Any]:
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        result: dict[str, Any] = await handler(conn, arguments, timezone)
        return result
    except Exception as exc:
        # Any failure is reported back to the model as a tool result (so it
        # can explain to the user), not raised — a bad tool call must not
        # crash the whole chat stream.
        return {"error": str(exc)}
