-- Open-Dev-Plan initial schema.
-- All timestamps are stored as ISO-8601 UTC strings with a trailing "Z"
-- (see odp.models.time). Never store naive local time — see plan §1/#6.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- projects
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'done', 'archived')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------- meetings
-- A meeting is also a calendar event. Recurrence uses an RFC-5545 RRULE
-- string so it round-trips losslessly through .ics export/import.
CREATE TABLE meetings (
    id                TEXT PRIMARY KEY,
    project_id        TEXT REFERENCES projects (id) ON DELETE SET NULL,
    title             TEXT NOT NULL,
    start_utc         TEXT NOT NULL,          -- ISO-8601 UTC, e.g. 2026-09-22T07:30:00Z
    end_utc           TEXT NOT NULL,
    timezone          TEXT NOT NULL,          -- IANA zone the user scheduled it in, e.g. Europe/Istanbul
    rrule             TEXT,                   -- RFC-5545 RRULE, NULL if not recurring
    location_link     TEXT,                   -- user-pasted link or generated Jitsi room URL
    participants_json TEXT NOT NULL DEFAULT '[]',
    audio_path        TEXT,                   -- relative path under data_dir/audio/
    status             TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'recorded', 'transcribing', 'transcribed', 'processed', 'cancelled')),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX idx_meetings_start ON meetings (start_utc);
CREATE INDEX idx_meetings_project ON meetings (project_id);

-- ------------------------------------------------------- transcript_segments
-- Segment-level transcript so the UI can jump audio playback to the exact
-- source of any AI-derived proposal (plan §5/§1 #5 provenance).
CREATE TABLE transcript_segments (
    id             TEXT PRIMARY KEY,
    meeting_id     TEXT NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,          -- ordering within the meeting
    start_ms       INTEGER NOT NULL,
    end_ms         INTEGER NOT NULL,
    text           TEXT NOT NULL,
    speaker        TEXT,                      -- NULL until diarization/manual labeling
    confidence     REAL,                      -- avg log-prob or similar, 0..1 normalized
    no_speech_prob REAL
);
CREATE INDEX idx_segments_meeting ON transcript_segments (meeting_id, seq);

-- Full-text search over transcript text (Turkish: remove_diacritics helps
-- with dotted/dotless I folding, see plan §8).
CREATE VIRTUAL TABLE transcript_segments_fts USING fts5 (
    text,
    content = 'transcript_segments',
    content_rowid = 'rowid',
    tokenize = "unicode61 remove_diacritics 2"
);
CREATE TRIGGER transcript_segments_ai AFTER INSERT ON transcript_segments BEGIN
    INSERT INTO transcript_segments_fts (rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER transcript_segments_ad AFTER DELETE ON transcript_segments BEGIN
    INSERT INTO transcript_segments_fts (transcript_segments_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER transcript_segments_au AFTER UPDATE ON transcript_segments BEGIN
    INSERT INTO transcript_segments_fts (transcript_segments_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
    INSERT INTO transcript_segments_fts (rowid, text) VALUES (new.rowid, new.text);
END;

-- ------------------------------------------------------------------- tasks
CREATE TABLE tasks (
    id                TEXT PRIMARY KEY,
    project_id        TEXT REFERENCES projects (id) ON DELETE SET NULL,
    meeting_id        TEXT REFERENCES meetings (id) ON DELETE SET NULL,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    owner             TEXT,
    due_utc           TEXT,
    status            TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'blocked')),
    -- Provenance: which transcript segment this task was derived from, and
    -- how confident the model was — required for fine-tuning data export
    -- (plan §7) and for the UI's "why was this suggested?" trace.
    source_segment_id TEXT REFERENCES transcript_segments (id) ON DELETE SET NULL,
    confidence        REAL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX idx_tasks_project ON tasks (project_id);
CREATE INDEX idx_tasks_meeting ON tasks (meeting_id);
CREATE INDEX idx_tasks_status ON tasks (status);

-- Task dependency graph for Gantt critical-path computation.
-- dep_type follows the four standard PM relations.
CREATE TABLE task_dependencies (
    id                 TEXT PRIMARY KEY,
    task_id            TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    depends_on_task_id TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    dep_type           TEXT NOT NULL DEFAULT 'FS' CHECK (dep_type IN ('FS', 'SS', 'FF', 'SF')),
    UNIQUE (task_id, depends_on_task_id)
);
CREATE INDEX idx_deps_task ON task_dependencies (task_id);
CREATE INDEX idx_deps_depends_on ON task_dependencies (depends_on_task_id);

-- --------------------------------------------------------------- proposals
-- Every AI-generated suggestion (action item, decision, summary, schedule
-- intent) lands here first. Nothing is written to a domain table until a
-- human approves it (plan §1/#5). Approved/edited proposals are the source
-- of SFT examples; rejected ones become DPO "rejected" completions (§7).
CREATE TABLE proposals (
    id                  TEXT PRIMARY KEY,
    kind                TEXT NOT NULL CHECK (kind IN ('task', 'decision', 'summary', 'schedule_intent')),
    payload_json        TEXT NOT NULL,        -- model's structured output, schema-validated
    source_meeting_id   TEXT REFERENCES meetings (id) ON DELETE CASCADE,
    source_segment_ids_json TEXT NOT NULL DEFAULT '[]',
    confidence          REAL,
    prompt_version      TEXT NOT NULL,
    model               TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'edited', 'rejected')),
    resolved_payload_json TEXT,               -- user's final version, if edited
    resolved_task_id    TEXT REFERENCES tasks (id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL,
    resolved_at         TEXT
);
CREATE INDEX idx_proposals_meeting ON proposals (source_meeting_id);
CREATE INDEX idx_proposals_status ON proposals (status);

-- ------------------------------------------------------------------- jobs
-- Background work (transcription, extraction, embedding, briefing) is
-- durable: a job row survives a process restart and can be resumed/queried.
CREATE TABLE jobs (
    id           TEXT PRIMARY KEY,
    job_type     TEXT NOT NULL CHECK (job_type IN ('transcription', 'extraction', 'embedding', 'briefing')),
    status       TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    progress     REAL NOT NULL DEFAULT 0.0,
    error        TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT
);
CREATE INDEX idx_jobs_status ON jobs (status);

-- ------------------------------------------------------------ prompt_cache
-- Keyed by hash(prompt_version + model + input) -> avoids re-running the
-- same LLM call twice (plan §6).
CREATE TABLE prompt_cache (
    cache_key     TEXT PRIMARY KEY,
    prompt_version TEXT NOT NULL,
    model         TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- ------------------------------------------------------------ embeddings
-- Vector store for hybrid search (FTS5 + cosine), keyed 1:1 with
-- transcript_segments.id. Populated lazily by the embedding job.
CREATE VIRTUAL TABLE segment_embeddings USING vec0 (
    segment_id TEXT PRIMARY KEY,
    embedding  FLOAT[1024]                    -- bge-m3 dense output size
);

-- ------------------------------------------------------- training_examples
-- Fine-tuning dataset source (plan §7). Populated whenever a proposal is
-- resolved (approved, edited, or rejected).
CREATE TABLE training_examples (
    id                   TEXT PRIMARY KEY,
    proposal_id          TEXT NOT NULL REFERENCES proposals (id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL CHECK (kind IN ('sft', 'dpo_pair')),
    transcript_excerpt   TEXT NOT NULL,
    model_output_json    TEXT NOT NULL,
    user_correction_json TEXT,                -- NULL if approved as-is
    created_at           TEXT NOT NULL
);
CREATE INDEX idx_training_examples_proposal ON training_examples (proposal_id);
