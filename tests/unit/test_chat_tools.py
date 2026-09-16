"""Covers services/chat/tools.py: full CRUD parity with the UI, the
delete-confirmation gate, and the checklist title-lookup tools."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from odp.models import ProposalKind, TaskStatus
from odp.models.time import from_utc_iso
from odp.repositories.customers import CustomersRepository
from odp.repositories.meetings import MeetingsRepository
from odp.repositories.projects import ProjectsRepository
from odp.repositories.proposals import ProposalsRepository
from odp.repositories.tasks import TasksRepository
from odp.services.chat.tools import TOOL_SCHEMAS, execute_tool
from odp.services.llm import FakeLLMProvider

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


# ============================================================ dependencies


async def test_add_task_dependency(db_conn):
    a = await execute_tool(db_conn, "create_task", {"title": "Tasarım"}, timezone=TZ)
    b = await execute_tool(db_conn, "create_task", {"title": "Geliştirme"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "add_task_dependency",
        {"task_id": b["task_id"], "depends_on_task_id": a["task_id"]},
        timezone=TZ,
    )
    assert result["result"] == "created"
    repo = TasksRepository(db_conn)
    deps = repo.list_dependencies_for_task(b["task_id"])
    assert [d.depends_on_task_id for d in deps] == [a["task_id"]]


async def test_add_task_dependency_rejects_self_dependency(db_conn):
    a = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "add_task_dependency",
        {"task_id": a["task_id"], "depends_on_task_id": a["task_id"]},
        timezone=TZ,
    )
    assert "error" in result


async def test_add_task_dependency_rejects_unknown_task(db_conn):
    a = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "add_task_dependency",
        {"task_id": a["task_id"], "depends_on_task_id": "nope"},
        timezone=TZ,
    )
    assert "error" in result


async def test_remove_task_dependency(db_conn):
    a = await execute_tool(db_conn, "create_task", {"title": "Tasarım"}, timezone=TZ)
    b = await execute_tool(db_conn, "create_task", {"title": "Geliştirme"}, timezone=TZ)
    await execute_tool(
        db_conn,
        "add_task_dependency",
        {"task_id": b["task_id"], "depends_on_task_id": a["task_id"]},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "remove_task_dependency",
        {"task_id": b["task_id"], "depends_on_task_id": a["task_id"]},
        timezone=TZ,
    )
    assert result["result"] == "deleted"
    assert TasksRepository(db_conn).list_dependencies_for_task(b["task_id"]) == []


async def test_remove_task_dependency_no_match_is_an_error(db_conn):
    a = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    b = await execute_tool(db_conn, "create_task", {"title": "Y"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "remove_task_dependency",
        {"task_id": b["task_id"], "depends_on_task_id": a["task_id"]},
        timezone=TZ,
    )
    assert "error" in result


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
        {"name": "Web Sitesi", "customer_ids": [customer["customer_id"]]},
        timezone=TZ,
    )
    project = ProjectsRepository(db_conn).get(result["project_id"])
    assert project is not None
    assert project.customer_ids == [customer["customer_id"]]


async def test_create_project_linked_to_multiple_customers(db_conn):
    c1 = await execute_tool(db_conn, "create_customer", {"name": "A"}, timezone=TZ)
    c2 = await execute_tool(db_conn, "create_customer", {"name": "B"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "create_project",
        {"name": "Ortak Proje", "customer_ids": [c1["customer_id"], c2["customer_id"]]},
        timezone=TZ,
    )
    project = ProjectsRepository(db_conn).get(result["project_id"])
    assert project is not None
    assert set(project.customer_ids) == {c1["customer_id"], c2["customer_id"]}


async def test_update_project_status_and_unlink_customer(db_conn):
    customer = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    project = await execute_tool(
        db_conn,
        "create_project",
        {"name": "X", "customer_ids": [customer["customer_id"]]},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_project",
        {"project_id": project["project_id"], "status": "paused", "customer_ids": []},
        timezone=TZ,
    )
    assert result["status"] == "paused"
    fetched = ProjectsRepository(db_conn).get(project["project_id"])
    assert fetched is not None
    assert fetched.customer_ids == []


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


async def test_create_meeting_can_link_a_customer_directly(db_conn):
    customer = await execute_tool(
        db_conn, "create_customer", {"name": "Gaziantep Sanayi Odası"}, timezone=TZ
    )
    result = await execute_tool(
        db_conn,
        "create_meeting",
        {"title": "İlk görüşme", "start_time": "10:00", "customer_id": customer["customer_id"]},
        timezone=TZ,
    )
    row = db_conn.execute("SELECT * FROM meetings WHERE id = ?", (result["meeting_id"],)).fetchone()
    assert row is not None
    assert row["customer_id"] == customer["customer_id"]


async def test_update_meeting_links_it_to_a_customer(db_conn):
    customer = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    meeting = await execute_tool(
        db_conn, "create_meeting", {"title": "X", "start_time": "10:00"}, timezone=TZ
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": meeting["meeting_id"], "customer_id": customer["customer_id"]},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    assert result["customer_id"] == customer["customer_id"]
    row = db_conn.execute(
        "SELECT * FROM meetings WHERE id = ?", (meeting["meeting_id"],)
    ).fetchone()
    assert row["customer_id"] == customer["customer_id"]


async def test_update_meeting_unlinks_customer_with_none_word(db_conn):
    customer = await execute_tool(db_conn, "create_customer", {"name": "Acme"}, timezone=TZ)
    meeting = await execute_tool(
        db_conn,
        "create_meeting",
        {"title": "X", "start_time": "10:00", "customer_id": customer["customer_id"]},
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": meeting["meeting_id"], "customer_id": "yok"},
        timezone=TZ,
    )
    assert result["customer_id"] is None


async def test_update_meeting_rejects_unknown_meeting_id(db_conn):
    result = await execute_tool(
        db_conn, "update_meeting", {"meeting_id": "nope", "title": "X"}, timezone=TZ
    )
    assert "error" in result


async def test_update_meeting_changes_start_time_keeps_day_and_duration(db_conn):
    created = await execute_tool(
        db_conn,
        "create_meeting",
        {
            "title": "X",
            "explicit_date": "2026-09-25",
            "start_time": "10:00",
            "duration_minutes": 60,
        },
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": created["meeting_id"], "start_time": "13:00"},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    local_start = from_utc_iso(result["start_utc"]).astimezone(ZoneInfo(TZ))
    local_end = from_utc_iso(result["end_utc"]).astimezone(ZoneInfo(TZ))
    assert local_start.date().isoformat() == "2026-09-25"
    assert (local_start.hour, local_start.minute) == (13, 0)
    assert local_end - local_start == timedelta(minutes=60)


async def test_update_meeting_changes_day_keeps_time_and_duration(db_conn):
    created = await execute_tool(
        db_conn,
        "create_meeting",
        {
            "title": "X",
            "explicit_date": "2026-09-25",
            "start_time": "10:00",
            "duration_minutes": 90,
        },
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": created["meeting_id"], "explicit_date": "2026-09-28"},
        timezone=TZ,
    )
    local_start = from_utc_iso(result["start_utc"]).astimezone(ZoneInfo(TZ))
    local_end = from_utc_iso(result["end_utc"]).astimezone(ZoneInfo(TZ))
    assert local_start.date().isoformat() == "2026-09-28"
    assert (local_start.hour, local_start.minute) == (10, 0)
    assert local_end - local_start == timedelta(minutes=90)


async def test_update_meeting_changes_duration_only(db_conn):
    created = await execute_tool(
        db_conn,
        "create_meeting",
        {
            "title": "X",
            "explicit_date": "2026-09-25",
            "start_time": "10:00",
            "duration_minutes": 60,
        },
        timezone=TZ,
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": created["meeting_id"], "duration_minutes": 30},
        timezone=TZ,
    )
    local_start = from_utc_iso(result["start_utc"]).astimezone(ZoneInfo(TZ))
    local_end = from_utc_iso(result["end_utc"]).astimezone(ZoneInfo(TZ))
    assert (local_start.hour, local_start.minute) == (10, 0)
    assert local_end - local_start == timedelta(minutes=30)


async def test_update_meeting_rejects_malformed_start_time(db_conn):
    created = await execute_tool(
        db_conn, "create_meeting", {"title": "X", "start_time": "10:00"}, timezone=TZ
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": created["meeting_id"], "start_time": "not-a-time"},
        timezone=TZ,
    )
    assert "error" in result


async def test_update_meeting_time_change_self_heals_a_corrupt_stored_duration(db_conn):
    # A meeting with an end time before its start (possible before the API
    # validated this — see meetings router) must not block a time fix
    # forever just because "preserve the existing duration" is nonsensical
    # here; it should fall back to a sane default instead of erroring.
    created = await execute_tool(
        db_conn,
        "create_meeting",
        {"title": "X", "explicit_date": "2026-09-25", "start_time": "10:00"},
        timezone=TZ,
    )
    MeetingsRepository(db_conn).update(
        created["meeting_id"],
        start_utc="2026-09-25T16:00:00Z",
        end_utc="2026-09-25T06:00:00Z",  # end before start
    )
    result = await execute_tool(
        db_conn,
        "update_meeting",
        {"meeting_id": created["meeting_id"], "start_time": "13:00"},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    local_start = from_utc_iso(result["start_utc"]).astimezone(ZoneInfo(TZ))
    local_end = from_utc_iso(result["end_utc"]).astimezone(ZoneInfo(TZ))
    assert (local_start.hour, local_start.minute) == (13, 0)
    assert local_end - local_start == timedelta(minutes=60)


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


async def test_suggest_meeting_slot_returns_conflict_free_slots(db_conn):
    provider = FakeLLMProvider()
    provider.add_json_response(
        "Çarşamba",
        {
            "duration_minutes": 90,
            "explicit_date": "2026-09-23",
            "day_of_week": None,
            "time_of_day_preference": "any",
            "earliest_local_time": None,
            "participant_hint": None,
        },
    )
    result = await execute_tool(
        db_conn,
        "suggest_meeting_slot",
        {"text": "Çarşamba 1.5 saatlik bir toplantı"},
        timezone=TZ,
        provider=provider,
        model="gpt-oss:20b",
    )
    assert result["result"] == "suggested"
    assert result["target_date"] == "2026-09-23"
    assert len(result["slots"]) >= 1


async def test_suggest_meeting_slot_requires_text(db_conn):
    result = await execute_tool(
        db_conn, "suggest_meeting_slot", {"text": ""}, timezone=TZ, provider=None, model=None
    )
    assert "error" in result


async def test_suggest_meeting_slot_without_provider_is_a_clean_error(db_conn):
    result = await execute_tool(
        db_conn,
        "suggest_meeting_slot",
        {"text": "Çarşamba 1.5 saatlik bir toplantı"},
        timezone=TZ,
    )
    assert "error" in result


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


async def test_execute_tool_accepts_generic_id_as_a_fallback_for_the_specific_key(db_conn):
    # Observed live: the model occasionally sends {"id": ...} instead of
    # the schema's {"task_id": ...} on an update/delete tool.
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn, "update_task", {"id": created["task_id"], "status": "done"}, timezone=TZ
    )
    assert result["result"] == "updated"


async def test_execute_tool_generic_id_fallback_does_not_override_the_specific_key(db_conn):
    created = await execute_tool(db_conn, "create_task", {"title": "X"}, timezone=TZ)
    result = await execute_tool(
        db_conn,
        "update_task",
        {"id": "wrong-id", "task_id": created["task_id"], "status": "done"},
        timezone=TZ,
    )
    assert result["result"] == "updated"
    assert result["task_id"] == created["task_id"]


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
