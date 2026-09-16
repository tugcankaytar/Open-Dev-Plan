# Contributing to Open-Dev-Plan

Thanks for considering a contribution! This is an early-stage project — expect rough edges.

## Setup

```bash
uv sync --group dev
uv run pre-commit install
```

You'll also want [Ollama](https://ollama.com) running locally with at least one model pulled (`ollama pull qwen3:14b` is a reasonable small default) to exercise anything beyond the deterministic tests.

## Workflow

1. Fork and branch off `main`.
2. Make your change. Keep it focused — smaller PRs review faster.
3. Run the checks locally before pushing:
   ```bash
   uv run ruff check . && uv run ruff format . && uv run mypy src
   uv run pytest -m "not gpu and not eval"
   ```
4. If you touched anything LLM-facing, prefer adding a `FakeLLMProvider`-based test (see `tests/unit/test_structured_llm.py`) over one that requires a live model, so CI can run it.
5. Open a PR describing *what* changed and *why*.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`) — it drives the changelog.

## Design principles (please read before large changes)

- **Nothing leaves the device.** No telemetry, no "phone home" defaults, no cloud fallback. Tests enforce this (`tests/conftest.py`'s network-ban fixture) — don't work around it.
- **The LLM proposes, the human disposes.** Any AI-derived task/decision/schedule change must land in the `proposals` table and wait for explicit user approval before touching a domain table. See `docs`/plan discussion in `src/odp/models/domain.py`'s `Proposal` model.
- **No LLM arithmetic.** Calendar conflict detection, critical-path computation, and similar deterministic logic must be plain code with unit tests — never "ask the model." This was the single biggest bug in the project's original draft plan; we don't want to reintroduce it.
- **Structured output only.** LLM responses that feed application logic go through `odp.services.llm.generate_structured` against a Pydantic schema — never regex over prose.

## Reporting bugs / requesting features

Use the issue templates. For security-sensitive reports, see [SECURITY.md](SECURITY.md) instead of opening a public issue.
