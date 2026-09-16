"""Validate LLM JSON output against a Pydantic model, with one repair pass.

Plan §1/#4: never regex-parse free text out of a model response. We ask
for constrained JSON (LLMProvider.generate_json) and validate the result;
if it's malformed we give the model exactly one chance to fix it by
showing it the validation error, then surface the raw text to the caller
rather than silently swallowing the failure.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ValidationError

from odp.services.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class StructuredGenerationError(Exception):
    """Raised when the model can't produce schema-valid JSON after a repair attempt.

    Carries the last raw response so the caller can show it to the user
    instead of failing silently (plan §1/#4).
    """

    def __init__(self, message: str, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


async def generate_structured[T: BaseModel](
    provider: LLMProvider,
    *,
    prompt: str,
    schema_model: type[T],
    model: str,
    system: str | None = None,
    reasoning_effort: str | None = None,
    temperature: float = 0.2,
) -> T:
    """Call the provider and validate its output against `schema_model`.

    Retries once with the validation error fed back to the model if the
    first response doesn't parse/validate.
    """
    json_schema = schema_model.model_json_schema()

    raw = await provider.generate_json(
        prompt=prompt,
        json_schema=json_schema,
        model=model,
        system=system,
        reasoning_effort=reasoning_effort,
        temperature=temperature,
    )

    try:
        return schema_model.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError) as first_error:
        logger.warning("structured output failed validation, retrying once: %s", first_error)

        repair_prompt = (
            f"{prompt}\n\n"
            f"Önceki cevabın şema doğrulamasından geçmedi:\n{first_error}\n\n"
            f"Önceki cevabın:\n{raw}\n\n"
            "Lütfen SADECE şemaya tam uyan geçerli\n"
            "bir JSON nesnesi döndür."
        )
        raw_retry = await provider.generate_json(
            prompt=repair_prompt,
            json_schema=json_schema,
            model=model,
            system=system,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
        )
        try:
            return schema_model.model_validate_json(raw_retry)
        except (ValidationError, json.JSONDecodeError) as second_error:
            name = schema_model.__name__
            raise StructuredGenerationError(
                f"model failed to produce valid {name} JSON after repair attempt: {second_error}",
                raw_response=raw_retry,
            ) from second_error
