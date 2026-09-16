-- Meetings can belong to a customer directly, independent of a project
-- (plenty of meetings — e.g. a first call with a prospect — happen before
-- any project exists). Nullable FK, same shape as projects.customer_id.

ALTER TABLE meetings ADD COLUMN customer_id TEXT REFERENCES customers (id) ON DELETE SET NULL;
CREATE INDEX idx_meetings_customer ON meetings (customer_id);
