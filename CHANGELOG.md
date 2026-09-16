# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Project skeleton: `uv`-managed Python package, FastAPI app, SQLite schema + migration runner (WAL, FTS5, sqlite-vec).
- Local LLM provider abstraction (`LLMProvider` Protocol) with an Ollama backend and an in-memory fake for tests.
- Structured-output generation with schema validation and a single repair pass.
- Durable, GPU-coordinated background job queue (`jobs` table + worker + single-slot GPU semaphore).
- `/api/health` endpoint reporting DB and Ollama/model availability.
- CI (lint, format check, type check, tests), pre-commit hooks, contribution/security docs.
- Data layer: repositories for projects, meetings (+ transcript segments), tasks (+ dependencies), and proposals.
- Deterministic scheduling engine (interval merge/conflict-detection + free-slot search) with an LLM used only to parse natural-language intent, never to compute dates or resolve conflicts itself.
- `.ics` calendar export/import with RRULE support, round-trip tested.
- Meeting extraction pipeline: versioned prompts, action-item/decision/summary extraction, map-reduce chunking for long transcripts, embedding-based dedup, and a proposal-only write path (nothing is ever written to a domain table without human approval).
- Proposal resolution (`approve`/`edit`/`reject`): turns an approved/edited task proposal into a real `Task` with a deterministically-resolved due date; every resolution is logged to `training_examples` for future fine-tuning.
- Full HTTP API (projects/tasks/meetings/calendar/proposals/schedule-suggest) plus an SSE job-progress stream, wired to a real background worker.
- Eval harness (`evals/`) comparing candidate extraction models on a small golden set; used to pick `gpt-oss:20b` as the default for both extraction and Turkish prose generation (see `evals/README.md`).
- Fine-tuning dataset export script (`training/export_dataset.py`) and a documented LoRA runbook (`training/README.md`).
- Live end-to-end test against real local models (`pytest -m gpu`), verifying the full meeting → extraction → proposal → approval → task flow.
- `POST /api/meetings/{id}/transcript/import-text`: paste/type a transcript to exercise the extraction pipeline before real audio transcription exists.
- React + TypeScript web UI (Vite, TanStack Query): dashboard, projects, meetings (with transcript paste, live extraction trigger, SSE job progress, and inline proposal approve/edit/reject), a task Kanban board, a natural-language scheduling assistant, and calendar import/export. Built and served as static files by the same FastAPI process (`uv run odp serve` alone is now a complete app); `npm run dev` for hot-reload development against a separately-running backend.
- Verified live end-to-end through the running app (not just tests): create a meeting → paste a Turkish transcript → real `gpt-oss:20b` extraction → review proposals → approve → confirm the resulting Task, including correct deterministic due-date resolution ("friday" → the correct calendar date).
