-- A project can now belong to more than one customer (a joint venture
-- between two clients, a shared internal+client project, etc.) — moves
-- the single nullable FK to a join table. Existing single links are
-- preserved before the old column is dropped.

CREATE TABLE project_customers (
    project_id  TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, customer_id)
);
CREATE INDEX idx_project_customers_customer ON project_customers (customer_id);

INSERT INTO project_customers (project_id, customer_id)
SELECT id, customer_id FROM projects WHERE customer_id IS NOT NULL;

DROP INDEX idx_projects_customer;
ALTER TABLE projects DROP COLUMN customer_id;
