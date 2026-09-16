"""Structured-output schemas for meeting extraction.

Note what's deliberately absent: no computed due date, no resolved
schedule time. `due_day_of_week` / `due_explicit_date` mirror
`ScheduleIntent` (plan §1/#1's split) — the model names a day, deterministic
code (odp.services.common.dates.resolve_weekday) turns it into a date.
`source_quote` on every item is the provenance trail the UI uses to jump
the transcript player to the right moment (plan §5/§1 #5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedActionItem(BaseModel):
    title: str
    owner: str | None = None
    due_day_of_week: str | None = Field(
        default=None, description="English weekday name if a day was named; never a computed date"
    )
    due_explicit_date: str | None = Field(
        default=None,
        description="ISO date YYYY-MM-DD only if an unambiguous calendar date was stated",
    )
    source_quote: str = Field(
        description="Verbatim quote from the transcript this was derived from"
    )
    confidence: float = Field(ge=0.0, le=1.0)


class ActionItemsExtraction(BaseModel):
    action_items: list[ExtractedActionItem]


class ExtractedDecision(BaseModel):
    summary: str
    source_quote: str
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionsExtraction(BaseModel):
    decisions: list[ExtractedDecision]
