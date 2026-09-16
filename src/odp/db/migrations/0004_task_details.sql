-- Richer task fields: priority, a start date alongside the existing due
-- date (useful groundwork for a future Gantt view), free-text tags, and
-- a checklist sub-table for breaking a task into smaller steps.

ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'urgent'));
ALTER TABLE tasks ADD COLUMN start_utc TEXT;
ALTER TABLE tasks ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]';

CREATE INDEX idx_tasks_priority ON tasks (priority);

CREATE TABLE task_checklist_items (
    id         TEXT PRIMARY KEY,
    task_id    TEXT NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    seq        INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_checklist_task ON task_checklist_items (task_id, seq);
