"""Application configuration.

All settings are file/env driven so the app runs the same from a dev
checkout, `uv tool install`, or Docker. Nothing here talks to the network
at import time.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """XDG-style per-user data directory, created on first access."""
    base = Path.home() / ".local" / "share" / "open-dev-plan"
    return base


def _default_config_dir() -> Path:
    base = Path.home() / ".config" / "open-dev-plan"
    return base


class Settings(BaseSettings):
    """Runtime configuration.

    Values can be overridden via environment variables prefixed ``ODP_``
    (e.g. ``ODP_OLLAMA_HOST=http://localhost:11434``) or a ``.env`` file in
    the working directory. See ``.env.example``.
    """

    model_config = SettingsConfigDict(env_prefix="ODP_", env_file=".env", extra="ignore")

    # --- Paths ---
    data_dir: Path = Field(default_factory=_default_data_dir)
    config_dir: Path = Field(default_factory=_default_config_dir)

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8765

    # --- Ollama / LLM ---
    ollama_host: str = "http://127.0.0.1:11434"
    # Structured extraction (action items, decisions, intent parsing): favors
    # speed + strict JSON-schema adherence over prose fluency.
    extraction_model: str = "gpt-oss:20b"
    # Turkish prose generation (summaries, daily briefs): favors fluent,
    # idiomatic Turkish over raw reasoning throughput.
    prose_model: str = "qwen3:14b"
    embedding_model: str = "bge-m3"
    llm_request_timeout_s: float = 120.0

    # --- Transcription ---
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    transcription_language: str = "tr"

    # --- Locale ---
    default_timezone: str = "Europe/Istanbul"

    # --- GPU coordination ---
    # Only one heavy GPU job (LLM generation, Whisper transcription, LoRA
    # training) may run at a time on a single 16GB-class card.
    gpu_concurrency: int = 1

    @property
    def db_path(self) -> Path:
        return self.data_dir / "odp.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
