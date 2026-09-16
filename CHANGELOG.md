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
