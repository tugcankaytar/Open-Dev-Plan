# Security Policy

## Data-locality guarantee

Open-Dev-Plan's core premise is that meeting audio, transcripts, and derived work data never leave your machine:

- The LLM runs through a local [Ollama](https://ollama.com) instance (`127.0.0.1` by default).
- Speech-to-text runs locally via `faster-whisper`.
- All persistent state lives in one local SQLite file (`~/.local/share/open-dev-plan/odp.db`) and a local audio directory — no remote database, no sync service.
- The test suite includes an autouse fixture (`tests/conftest.py::_no_network`) that raises if any code path attempts a socket connection to a non-localhost address. A PR that needs to be exempted from this must justify why in review — it should be exceptional, not routine.

Optional features that *do* reach the network (e.g. a future real Zoom/Google Calendar integration) will be opt-in, clearly labeled in the UI, and never enabled by default.

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability. Instead, use GitHub's [private vulnerability reporting](../../security/advisories/new) for this repository. We'll acknowledge reports within a few days.

## Threat model notes

- This is a **single-user, single-machine, localhost-bound** application by default. It is not designed to be exposed directly to an untrusted network — if you bind it beyond `127.0.0.1`, put a reverse proxy with authentication in front of it.
- Audio recordings and transcripts are sensitive personal/business data by nature. `.gitignore` and a pre-commit hook block committing `*.wav`/`*.db`/etc., but you are responsible for not exporting/sharing generated `.ics`, PDF, or JSON exports carelessly.
- Fine-tuning (see `training/`) reads your own approved/corrected task data to build a local training set. That dataset stays on disk under `training/` (gitignored) unless you explicitly export or share it.
