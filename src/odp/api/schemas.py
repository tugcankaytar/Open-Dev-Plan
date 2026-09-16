"""Request/response bodies for the HTTP API.

Separate from odp.models.domain because create/update requests omit
server-assigned fields (id, timestamps) and need their own validation
shape — reusing the domain models directly for requests would let a
client set `id` or `created_at`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from odp.models import DependencyType, ProjectStatus, TaskPriority, TaskStatus


class CustomerCreate(BaseModel):
    name: str
    description: str = ""


class CustomerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    customer_id: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    customer_id: str | None = None


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    owner: str | None = None
    due_utc: str | None = None
    start_utc: str | None = None
    priority: TaskPriority = TaskPriority.medium
    tags: list[str] = []
    project_id: str | None = None
    meeting_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    due_utc: str | None = None
    start_utc: str | None = None
    priority: TaskPriority | None = None
    tags: list[str] | None = None
    status: TaskStatus | None = None
    project_id: str | None = None


class ChecklistItemCreate(BaseModel):
    title: str


class ChecklistItemUpdate(BaseModel):
    done: bool


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: str
    dep_type: DependencyType = DependencyType.finish_to_start


class MeetingCreate(BaseModel):
    title: str
    start_utc: str
    end_utc: str
    timezone: str
    project_id: str | None = None
    rrule: str | None = None
    location_link: str | None = None
    participants: list[str] = []


class ProposalResolveRequest(BaseModel):
    action: Literal["approve", "edit", "reject"]
    payload: dict[str, Any] | None = None


class ScheduleSuggestRequest(BaseModel):
    text: str


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurnIn] = []


class TranscriptImportRequest(BaseModel):
    text: str


class IcsImportRequest(BaseModel):
    ics_text: str
    persist: bool = False


class DailyActivity(BaseModel):
    date: str
    created: int
    completed: int


class DashboardStats(BaseModel):
    active_projects: int
    open_tasks: int
    overdue_tasks: int
    meetings: int
    pending_proposals: int
    task_status_counts: dict[str, int]
    weekly_activity: list[DailyActivity]


class TimeSlotOut(BaseModel):
    start_utc: str
    end_utc: str


class ScheduleSuggestResponse(BaseModel):
    target_date: str
    duration_minutes: int
    participant_hint: str | None
    slots: list[TimeSlotOut]
