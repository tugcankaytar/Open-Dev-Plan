"""Natural-language scheduling intent → structured constraint.

The LLM's job stops at parsing: "Çarşamba, 1.5 saat, X ile" becomes a
`ScheduleIntent` (duration + a *name* for the target day, never a computed
date). Resolving "Wednesday" to an actual calendar date is deterministic
arithmetic in `resolve_target_date` — this split is the fix for the draft
plan's date bug (it called 2026-09-22 "Friday"; it's a Tuesday).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from odp.services.common.dates import resolve_weekday
from odp.services.llm.provider import LLMProvider
from odp.services.llm.structured import generate_structured

PROMPT_VERSION = "schedule_intent.v1"


class ScheduleIntent(BaseModel):
    """What the user asked for, with dates left unresolved.

    Only ONE of `explicit_date` / `day_of_week` should be set by the
    model; if both are absent, the caller falls back to "today or the
    next working day."
    """

    duration_minutes: int = Field(gt=0, le=8 * 60)
    explicit_date: str | None = Field(
        default=None, description="ISO date YYYY-MM-DD, only if the user gave an unambiguous date"
    )
    day_of_week: str | None = Field(
        default=None,
        description="English weekday name, only if the user referred to a weekday by name",
    )
    time_of_day_preference: Literal["morning", "afternoon", "evening", "any"] = "any"
    earliest_local_time: str | None = Field(
        default=None, description="HH:MM 24h, only if the user gave an explicit earliest bound"
    )
    participant_hint: str | None = Field(
        default=None, description="Name/company mentioned for the other participant, if any"
    )


_SYSTEM_PROMPT = (
    "Sen bir toplantı planlama asistanısın. Kullanıcının doğal dil isteğinden "
    "SADECE bir zaman kısıtı çıkar. Tarih HESAPLAMA — 'Çarşamba' gibi bir gün adı "
    "geçiyorsa day_of_week alanına İngilizce gün adını yaz (örn. 'wednesday'), "
    "explicit_date'i BOŞ bırak. Kullanıcı açıkça bir takvim tarihi verdiyse "
    "(örn. '22 Eylül') explicit_date'e ISO formatında yaz. İkisini birden doldurma."
)


async def parse_schedule_intent(provider: LLMProvider, *, text: str, model: str) -> ScheduleIntent:
    prompt = f'Kullanıcı isteği: "{text}"'
    return await generate_structured(
        provider,
        prompt=prompt,
        schema_model=ScheduleIntent,
        model=model,
        system=_SYSTEM_PROMPT,
        reasoning_effort="low",
    )


def resolve_target_date(intent: ScheduleIntent, reference_date: date) -> date:
    """Turn `explicit_date`/`day_of_week` into a concrete date — pure code.

    - An explicit date wins if present and parses.
    - A weekday name resolves to its next occurrence on/after
      `reference_date` (today counts if it's the same weekday).
    - Neither given → `reference_date` itself.
    """
    if intent.explicit_date:
        return date.fromisoformat(intent.explicit_date)

    if intent.day_of_week:
        try:
            return resolve_weekday(intent.day_of_week, reference_date)
        except ValueError as exc:
            msg = f"unrecognized day_of_week from model: {intent.day_of_week!r}"
            raise ValueError(msg) from exc

    return reference_date
