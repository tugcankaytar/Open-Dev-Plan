"""Versioned prompt loader.

Prompt text lives in plain files under `v1/`, `v2/`, etc — not inline in
Python — so a prompt change is a reviewable diff on its own, and every
`Proposal` row can record exactly which prompt (name + version + content
hash) produced it. That triple is what makes "why did the model suggest
this?" answerable months later, and it's the join key for building a
fine-tuning dataset per prompt version (plan §7).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_ROOT = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    text: str
    content_hash: str

    @property
    def prompt_version(self) -> str:
        """Compact identifier stored on every Proposal (plan §1/#5)."""
        return f"{self.name}/{self.version}/{self.content_hash[:8]}"


@lru_cache(maxsize=64)
def load_prompt(name: str, version: str = "v1") -> PromptTemplate:
    path = PROMPTS_ROOT / version / f"{name}.md"
    text = path.read_text(encoding="utf-8").strip()
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return PromptTemplate(name=name, version=version, text=text, content_hash=content_hash)
