-- Customers: the same shape as `projects` (name + description), since a
-- project optionally belongs to one customer. Nullable FK — plenty of
-- projects are internal and have no client.

CREATE TABLE customers (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

ALTER TABLE projects ADD COLUMN customer_id TEXT REFERENCES customers (id) ON DELETE SET NULL;
CREATE INDEX idx_projects_customer ON projects (customer_id);
