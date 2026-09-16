-- Small key/value store for settings the user changes at runtime from the
-- UI (currently: which Ollama model is active) — distinct from odp.config
-- .env-based Settings, which are process-startup defaults. A DB row here
-- overrides the .env default until changed again or the row is cleared.

CREATE TABLE app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
