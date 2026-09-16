from __future__ import annotations

from odp.models import TaskStatus
from odp.repositories.tasks import TasksRepository
from odp.services.chat.tools import execute_tool

TZ = "Europe/Istanbul"


def test_create_task_writes_a_real_task(db_conn):
    result = execute_tool(
        db_conn, "create_task", {"title": "Demo hazırla", "owner": "Mehmet"}, timezone=TZ
    )

    assert result["result"] == "created"
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.title == "Demo hazırla"
    assert task.owner == "Mehmet"


def test_create_task_requires_a_title(db_conn):
    result = execute_tool(db_conn, "create_task", {"title": ""}, timezone=TZ)
    assert "error" in result


def test_create_task_normalizes_turkish_priority_aliases(db_conn):
    result = execute_tool(db_conn, "create_task", {"title": "X", "priority": "Acil"}, timezone=TZ)
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.priority.value == "urgent"


def test_create_task_resolves_weekday_deterministically(db_conn):
    # 2026-09-16 is a Wednesday; asking the tool to resolve "friday" must
    # never involve the model computing a date itself (plan §1/#1).
    result = execute_tool(
        db_conn, "create_task", {"title": "X", "due_day_of_week": "friday"}, timezone=TZ
    )
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.due_utc is not None
    # Resolved date should be on/after "today" and land on a Friday in TZ.
    from zoneinfo import ZoneInfo

    from odp.models.time import from_utc_iso

    local_due = from_utc_iso(task.due_utc).astimezone(ZoneInfo(TZ))
    assert local_due.weekday() == 4  # Friday


def test_update_task_status_changes_real_task(db_conn):
    created = execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = execute_tool(
        db_conn,
        "update_task_status",
        {"task_id": created["task_id"], "status": "done"},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    task = TasksRepository(db_conn).get(created["task_id"])
    assert task is not None
    assert task.status == TaskStatus.done


def test_update_task_status_rejects_unknown_task_id(db_conn):
    result = execute_tool(
        db_conn, "update_task_status", {"task_id": "does-not-exist", "status": "done"}, timezone=TZ
    )
    assert "error" in result


def test_update_task_status_rejects_unrecognized_status(db_conn):
    created = execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = execute_tool(
        db_conn,
        "update_task_status",
        {"task_id": created["task_id"], "status": "flying"},
        timezone=TZ,
    )
    assert "error" in result


def test_add_checklist_item_to_real_task(db_conn):
    created = execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Wireframe"},
        timezone=TZ,
    )
    assert result["result"] == "created"
    items = TasksRepository(db_conn).list_checklist_items(created["task_id"])
    assert [i.title for i in items] == ["Wireframe"]


def test_add_checklist_item_rejects_unknown_task(db_conn):
    result = execute_tool(
        db_conn, "add_checklist_item", {"task_id": "nope", "title": "x"}, timezone=TZ
    )
    assert "error" in result


def test_create_meeting_writes_a_real_meeting(db_conn):
    result = execute_tool(
        db_conn,
        "create_meeting",
        {
            "title": "Planlama",
            "explicit_date": "2026-09-25",
            "start_time": "10:30",
            "duration_minutes": 90,
        },
        timezone=TZ,
    )
    assert result["result"] == "created"
    row = db_conn.execute("SELECT * FROM meetings WHERE id = ?", (result["meeting_id"],)).fetchone()
    assert row is not None
    assert row["title"] == "Planlama"


def test_create_meeting_requires_title_and_start_time(db_conn):
    result = execute_tool(db_conn, "create_meeting", {"title": "X"}, timezone=TZ)
    assert "error" in result


def test_create_meeting_rejects_malformed_start_time(db_conn):
    result = execute_tool(
        db_conn, "create_meeting", {"title": "X", "start_time": "not-a-time"}, timezone=TZ
    )
    assert "error" in result


def test_execute_tool_unknown_name_returns_error_not_raise(db_conn):
    result = execute_tool(db_conn, "delete_everything", {}, timezone=TZ)
    assert "error" in result


def test_no_delete_tool_is_exposed():
    from odp.services.chat.tools import TOOL_SCHEMAS

    names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    assert not any("delete" in name for name in names)
