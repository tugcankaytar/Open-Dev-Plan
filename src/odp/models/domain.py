"""Core domain models (Pydantic v2).

These double as API request/response schemas and as the shape LLM
structured-output is validated against (plan §3 "Doğrulama" row) — one
source of truth for both.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid4().hex


class ProjectStatus(StrEnum):
    active = "active"
    paused = "paused"
    done = "done"
    archived = "archived"


class MeetingStatus(StrEnum):
    scheduled = "scheduled"
    recorded = "recorded"
    transcribing = "transcribing"
    transcribed = "transcribed"
    processed = "processed"
    cancelled = "cancelled"


class TaskStatus(StrEnum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"


class TaskPriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class DependencyType(StrEnum):
    finish_to_start = "FS"
    start_to_start = "SS"
    finish_to_finish = "FF"
    start_to_finish = "SF"


class ProposalKind(StrEnum):
    task = "task"
    decision = "decision"
    summary = "summary"
    schedule_intent = "schedule_intent"


class ProposalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"


class JobType(StrEnum):
    transcription = "transcription"
    extraction = "extraction"
    embedding = "embedding"
    briefing = "briefing"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Customer(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: str = ""
    created_at: str
    updated_at: str


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    customer_ids: list[str] = Field(default_factory=list)
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.active
    created_at: str
    updated_at: str


class Meeting(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str | None = None
    customer_id: str | None = None
    title: str
    start_utc: str
    end_utc: str
    timezone: str
    rrule: str | None = None
    location_link: str | None = None
    participants: list[str] = Field(default_factory=list)
    audio_path: str | None = None
    status: MeetingStatus = MeetingStatus.scheduled
    created_at: str
    updated_at: str


class TranscriptSegment(BaseModel):
    id: str = Field(default_factory=new_id)
    meeting_id: str
    seq: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float | None = None
    no_speech_prob: float | None = None


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str | None = None
    meeting_id: str | None = None
    title: str
    description: str = ""
    owner: str | None = None
    due_utc: str | None = None
    start_utc: str | None = None
    priority: TaskPriority = TaskPriority.medium
    tags: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.todo
    source_segment_id: str | None = None
    confidence: float | None = None
    created_at: str
    updated_at: str
    # Computed by the repository (a checklist-items aggregate), not stored
    # on this row — present so a Kanban card can show "2/5" without an
    # extra request per task.
    checklist_total: int = 0
    checklist_done: int = 0


class TaskDependency(BaseModel):
    id: str = Field(default_factory=new_id)
    task_id: str
    depends_on_task_id: str
    dep_type: DependencyType = DependencyType.finish_to_start


class ChecklistItem(BaseModel):
    id: str = Field(default_factory=new_id)
    task_id: str
    title: str
    done: bool = False
    seq: int
    created_at: str


class Proposal(BaseModel):
    """An AI-generated suggestion awaiting human approval (plan §1/#5)."""

    id: str = Field(default_factory=new_id)
    kind: ProposalKind
    payload: dict[str, Any]
    source_meeting_id: str | None = None
    source_segment_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None
    prompt_version: str
    model: str
    status: ProposalStatus = ProposalStatus.pending
    resolved_payload: dict[str, Any] | None = None
    resolved_task_id: str | None = None
    created_at: str
    resolved_at: str | None = None


class Job(BaseModel):
    id: str = Field(default_factory=new_id)
    job_type: JobType
    status: JobStatus = JobStatus.queued
    payload: dict[str, Any] = Field(default_factory=dict)
    progress: float = 0.0
    error: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
