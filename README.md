<div align="center">

# Open-Dev-Plan

**A local-LLM powered work planner: turn meeting audio into tracked tasks, decisions, and a schedule — with your data never leaving your machine.**

[Türkçe README](README.tr.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

</div>

---

## Why local?

Meeting audio and business plans are some of the most sensitive data a small team produces. Open-Dev-Plan runs its LLM (via [Ollama](https://ollama.com)), speech-to-text (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)), and storage (a single SQLite file) entirely on your own hardware. No API keys, no cloud bill, no transcript ever crossing the network — this is enforced in CI, not just promised in this paragraph (see [`tests/conftest.py`](tests/conftest.py)).

## What it does

- **Record or import a meeting** → local Whisper transcription, tuned for Turkish, with a hallucination filter and a segment-level player.
- **Extract action items & decisions** with a local LLM, constrained to a JSON schema — every suggestion lands as a *proposal* you approve, edit, or reject before it becomes a real task (nothing is written automatically).
- **Track work** on a Kanban board and a dependency-aware Gantt chart (critical path included).
- **Schedule meetings** from natural language ("Wednesday, 1.5h with client X") — the LLM only parses your intent; free/busy conflict resolution is deterministic code, not a model guess.
- **Export/import `.ics`** calendars, including recurring meetings (RRULE).
- **Search across every past meeting** with hybrid full-text + semantic search.
- **Fine-tune** the extraction model on your own corrections (opt-in, local, via LoRA).

## Status

🚧 Early development, but the core loop works end-to-end today and is covered by tests (including a live run against real local models — see `evals/README.md`).

**Working now:** SQLite schema + migrations · local-LLM provider abstraction (Ollama, schema-constrained JSON output) · durable/GPU-coordinated job queue · meeting → structured extraction pipeline (action items, decisions, summary), with every result landing as a human-reviewed *proposal*, never written to a domain table automatically · deterministic (non-LLM) meeting scheduler and conflict detection · `.ics` export/import with RRULE · full HTTP API + SSE job progress · an eval harness that picks the extraction model from data, not assumption · a fine-tuning dataset export script that reads your own approved/corrected proposals.

**Not yet built:** the web UI (Kanban/Gantt/calendar views — the API is ready, the frontend isn't) · live meeting recording + Whisper transcription (only manual transcript import is wired up so far) · hybrid full-text/semantic search · daily briefing/reports · an installer/setup wizard. See `CHANGELOG.md` for what's landed release by release.

## Hardware

| VRAM | Suggested models |
|------|-------------------|
| 8 GB | `qwen3:8b` (or smaller), `faster-whisper` medium |
| 16 GB | `gpt-oss:20b` for both extraction and Turkish prose (see `evals/README.md` for why one model suffices), `faster-whisper` large-v3-turbo |
| 24 GB+ | Larger variants of the above, or `gpt-oss:120b` in low-VRAM offload mode |

CPU-only works but transcription and generation will be noticeably slower.

## Quickstart

```bash
# 1. Install Ollama and pull the models you plan to use
ollama pull gpt-oss:20b   # extraction + Turkish prose (see evals/README.md)
ollama pull bge-m3        # embeddings for search

# 2. Install and run Open-Dev-Plan (uv manages the Python environment)
uv sync
uv run odp serve
```

This opens `http://127.0.0.1:8765` in your browser. First run walks you through checking Ollama connectivity, model availability, GPU detection, and audio device selection.

## Development

```bash
uv sync --group dev
uv run ruff check .
uv run mypy src
uv run pytest -m "not gpu and not eval"
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, and [SECURITY.md](SECURITY.md) for the data-locality threat model.

## License

[Apache License 2.0](LICENSE).
