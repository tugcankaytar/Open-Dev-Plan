"""CRUD for the `customers` table."""

from __future__ import annotations

import sqlite3

from odp.models import Customer, new_id
from odp.models.time import utc_now_iso


class CustomersRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, name: str, description: str = "") -> Customer:
        now = utc_now_iso()
        customer = Customer(
            id=new_id(), name=name, description=description, created_at=now, updated_at=now
        )
        self._conn.execute(
            "INSERT INTO customers (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer.id, customer.name, customer.description, now, now),
        )
        return customer

    def get(self, customer_id: str) -> Customer | None:
        row = self._conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return self._row_to_customer(row) if row else None

    def list(self) -> list[Customer]:
        rows = self._conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
        return [self._row_to_customer(row) for row in rows]

    def update(
        self, customer_id: str, *, name: str | None = None, description: str | None = None
    ) -> Customer | None:
        existing = self.get(customer_id)
        if existing is None:
            return None
        name = existing.name if name is None else name
        description = existing.description if description is None else description
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE customers SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, now, customer_id),
        )
        return self.get(customer_id)

    def delete(self, customer_id: str) -> None:
        self._conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    @staticmethod
    def _row_to_customer(row: sqlite3.Row) -> Customer:
        return Customer(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
