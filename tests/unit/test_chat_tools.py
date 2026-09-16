"""Covers services/chat/tools.py: full CRUD parity with the UI, the
delete-confirmation gate, and the checklist title-lookup tools."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from odp.models import ProposalKind, TaskStatus
from odp.models.time import from_utc_iso
from odp.repositories.customers import CustomersRepository
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.tasks import TasksRepository
from odp.services.chat.tools import TOOL_SCHEMAS, execute_tool

TZ = "Europe/Istanbul"


# ==================================================================== tasks


async def test_create_task_writes_a_real_task(db_conn):
    result = await execute_tool(
        db_conn, "create_task", {"title": "Demo hazırla", "owner": "Mehmet"}, timezone=TZ
    )

    assert result["result"] == "created"
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.title == "Demo hazırla"
    assert task.owner == "Mehmet"


async def test_create_task_requires_a_title(db_conn):
    result = await execute_tool(db_conn, "create_task", {"title": ""}, timezone=TZ)
    assert "error" in result


async def test_create_task_normalizes_turkish_priority_aliases(db_conn):
    result = await execute_tool(
        db_conn, "create_task", {"title": "X", "priority": "Acil"}, timezone=TZ
    )
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.priority.value == "urgent"


async def test_create_task_resolves_weekday_deterministically(db_conn):
    # 2026-09-16 is a Wednesday; asking the tool to resolve "friday" must
    # never involve the model computing a date itself (plan §1/#1).
    result = await execute_tool(
        db_conn, "create_task", {"title": "X", "due_day_of_week": "friday"}, timezone=TZ
    )
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.due_utc is not None
    local_due = from_utc_iso(task.due_utc).astimezone(ZoneInfo(TZ))
    assert local_due.weekday() == 4  # Friday


async def test_create_task_accepts_description_tags_and_start_date(db_conn):
    result = await execute_tool(
        db_conn,
        "create_task",
        {
            "title": "X",
            "description": "detaylar",
            "tags": ["backend", "acil"],
            "start_day_of_week": "monday",
        },
        timezone=TZ,
    )
    task = TasksRepository(db_conn).get(result["task_id"])
    assert task is not None
    assert task.description == "detaylar"
    assert task.tags == ["backend", "acil"]
    assert task.start_utc is not None


async def test_update_task_changes_status(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "update_task", {"task_id": created["task_id"], "status": "done"}, timezone=TZ
    )
    assert result["result"] == "updated"
    task = TasksRepository(db_conn).get(created["task_id"])
    assert task is not None
    assert task.status == TaskStatus.done


async def test_update_task_replaces_tags_wholesale(db_conn):
    created = await execute_tool(
        db_conn, "create_task", {"title": "X", "tags": ["a", "b"]}, timezone=TZ
    )
    await execute_tool(
        db_conn, "update_task", {"task_id": created["task_id"], "tags": ["c"]}, timezone=TZ
    )
    task = TasksRepository(db_conn).get(created["task_id"])
    assert task is not None
    assert task.tags == ["c"]


async def test_update_task_rejects_unknown_task_id(db_conn):
    result = await execute_tool(
        db_conn, "update_task", {"task_id": "does-not-exist", "status": "done"}, timezone=TZ
    )
    assert "error" in result


async def test_update_task_rejects_unrecognized_status(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "update_task", {"task_id": created["task_id"], "status": "flying"}, timezone=TZ
    )
    assert "error" in result


async def test_delete_task_refuses_without_confirmation(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "delete_task", {"task_id": created["task_id"]}, timezone=TZ
    )
    assert "error" in result
    assert TasksRepository(db_conn).get(created["task_id"]) is not None  # not deleted


async def test_delete_task_refuses_with_confirmed_false(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "delete_task", {"task_id": created["task_id"], "confirmed": False}, timezone=TZ
    )
    assert "error" in result
    assert TasksRepository(db_conn).get(created["task_id"]) is not None


async def test_delete_task_succeeds_when_confirmed(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "delete_task", {"task_id": created["task_id"], "confirmed": True}, timezone=TZ
    )
    assert result["result"] == "deleted"
    assert TasksRepository(db_conn).get(created["task_id"]) is None


# ================================================================ checklist


async def test_add_checklist_item_to_real_task(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Wireframe"},
        timezone=TZ,
    )
    assert result["result"] == "created"
    items = TasksRepository(db_conn).list_checklist_items(created["task_id"])
    assert [i.title for i in items] == ["Wireframe"]


async def test_add_checklist_item_rejects_unknown_task(db_conn):
    result = await execute_tool(
        db_conn, "add_checklist_item", {"task_id": "nope", "title": "x"}, timezone=TZ
    )
    assert "error" in result


async def test_toggle_checklist_item_by_title(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    await execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Wireframe çiz"},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "toggle_checklist_item",
        {"task_id": created["task_id"], "item_title": "wireframe", "done": True},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    items = TasksRepository(db_conn).list_checklist_items(created["task_id"])
    assert items[0].done is True


async def test_toggle_checklist_item_no_match_is_an_error(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "toggle_checklist_item",
        {"task_id": created["task_id"], "item_title": "nonexistent", "done": True},
        timezone=TZ,
    )
    assert "error" in result


async def test_toggle_checklist_item_ambiguous_match_is_an_error(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    await execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Renk A"},
        timezone=TZ,
    )
    await execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Renk B"},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "toggle_checklist_item",
        {"task_id": created["task_id"], "item_title": "renk", "done": True},
        timezone=TZ,
    )
    assert "error" in result


async def test_delete_checklist_item_does_not_require_confirmation(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    await execute_tool(
        db_conn,
        "add_checklist_item",
        {"task_id": created["task_id"], "title": "Wireframe"},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "delete_checklist_item",
        {"task_id": created["task_id"], "item_title": "Wireframe"},
        timezone=TZ,
    )
    assert result["result"] == "deleted"
    assert TasksRepository(db_conn).list_checklist_items(created["task_id"]) == []


# =============================================================== customers


async def test_create_customer(db_conn):
    result = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    assert result["result"] == "created"
    assert CustomersRepository(db_conn).get(result["customer_id"]) is not None


async def test_update_customer(db_conn):
    created = await execute_tool(db_conn, "create_customer", {"name": "Eski"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "update_customer",
        {"customer_id": created["customer_id"], "name": "Yeni"},
        timezone=TZ,
    )
    assert result["name"] == "Yeni"


async def test_delete_customer_requires_confirmation(db_conn):
    created = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    denied = await execute_tool(
        db_conn, "delete_customer", {"customer_id": created["customer_id"]}, timezone=TZ
    )
    assert "error" in denied
    approved = await execute_tool(
        db_conn,
        "delete_customer",
        {"customer_id": created["customer_id"], "confirmed": True},
        timezone=TZ,
    )
    assert approved["result"] == "deleted"
    assert CustomersRepository(db_conn).get(created["customer_id"]) is None


# ================================================================ projects


async def test_create_project_linked_to_customer(db_conn):
    customer = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "create_project",
        {"name": "Web Sitesi", "customer_id": customer["customer_id"]},
        timezone=TZ,
    )
    project = ProjectsRepository(db_conn).get(result["project_id"])
    assert project is not None
    assert project.customer_id == customer["customer_id"]


async def test_update_project_status_and_unlink_customer(db_conn):
    customer = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    project = await execute_tool(
        db_conn,
        "create_project",
        {"name": "X", "customer_id": customer["customer_id"]},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_project",
        {"project_id": project["project_id"], "status": "paused", "customer_id": "yok"},
        timezone=TZ,
    )
    assert result["status"] == "paused"
    fetched = ProjectsRepository(db_conn).get(project["project_id"])
    assert fetched is not None
    assert fetched.customer_id is None


async def test_delete_project_requires_confirmation(db_conn):
    created = await execute_tool(db_conn, "create_project", {"name": "X"}, timezone=TZ)
    denied = await execute_tool(
        db_conn, "delete_project", {"project_id": created["project_id"]}, timezone=TZ
    )
    assert "error" in denied
    approved = await execute_tool(
        db_conn,
        "delete_project",
        {"project_id": created["project_id"], "confirmed": True},
        timezone=TZ,
    )
    assert approved["result"] == "deleted"


# ================================================================ meetings


async def test_create_meeting_writes_a_real_meeting(db_conn):
    result = await execute_tool(
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


async def test_create_meeting_requires_title_and_start_time(db_conn):
    result = await execute_tool(db_conn, "create_meeting", {"title": "X"}, timezone=TZ)
    assert "error" in result


async def test_create_meeting_rejects_malformed_start_time(db_conn):
    result = await execute_tool(
        db_conn, "create_meeting", {"title": "X", "start_time": "not-a-time"}, timezone=TZ
    )
    assert "error" in result


async def test_delete_meeting_requires_confirmation(db_conn):
    created = await execute_tool(
        db_conn, "create_meeting", {"title": "X", "start_time": "10:00"}, timezone=TZ
    )
    denied = await execute_tool(
        db_conn, "delete_meeting", {"meeting_id": created["meeting_id"]}, timezone=TZ
    )
    assert "error" in denied
    approved = await execute_tool(
        db_conn,
        "delete_meeting",
        {"meeting_id": created["meeting_id"], "confirmed": True},
        timezone=TZ,
    )
    assert approved["result"] == "deleted"
    assert MeetingsRepository(db_conn).get(created["meeting_id"]) is None


# =============================================================== proposals


async def test_resolve_proposal_approve_creates_task(db_conn):
    proposal = ProposalsRepository(db_conn).create(
        kind=ProposalKind.task,
        payload={"title": "Demo hazırla", "confidence": 0.9},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.9,
        prompt_version="v1",
        model="gpt-oss:20b",
    )
    result = await execute_tool(
        db_conn, "resolve_proposal", {"proposal_id": proposal.id, "action": "approve"}, timezone=TZ
    )
    assert result["result"] == "resolved"
    assert result["resolved_task_id"] is not None


async def test_resolve_proposal_reject(db_conn):
    proposal = ProposalsRepository(db_conn).create(
        kind=ProposalKind.decision,
        payload={"summary": "x", "confidence": 0.5},
        source_meeting_id=None,
        source_segment_ids=[],
        confidence=0.5,
        prompt_version="v1",
        model="gpt-oss:20b",
    )
    result = await execute_tool(
        db_conn, "resolve_proposal", {"proposal_id": proposal.id, "action": "reject"}, timezone=TZ
    )
    assert result["status"] == "rejected"


async def test_resolve_proposal_invalid_action(db_conn):
    result = await execute_tool(
        db_conn, "resolve_proposal", {"proposal_id": "whatever", "action": "maybe"}, timezone=TZ
    )
    assert "error" in result


# =================================================================== misc


async def test_execute_tool_unknown_name_returns_error_not_raise(db_conn):
    result = await execute_tool(db_conn, "delete_everything", {}, timezone=TZ)
    assert "error" in result


def test_delete_tools_all_require_confirmed_in_schema():
    delete_tool_names = {
        "delete_customer",
        "delete_project",
        "delete_task",
        "delete_meeting",
    }
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        if fn["name"] in delete_tool_names:
            assert "confirmed" in fn["parameters"]["required"], fn["name"]


def test_checklist_item_deletion_does_not_require_confirmation_in_schema():
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == "delete_checklist_item":
            assert "confirmed" not in schema["function"]["parameters"]["properties"]
