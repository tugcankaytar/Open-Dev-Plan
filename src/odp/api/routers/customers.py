from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from odp.api.deps import get_db
from odp.api.schemas import CustomerCreate, CustomerUpdate
from odp.models import Customer
from odp.repositories.customers import CustomersRepository

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.post("", response_model=Customer, status_code=201)
def create_customer(body: CustomerCreate, conn: sqlite3.Connection = Depends(get_db)) -> Customer:
    return CustomersRepository(conn).create(body.name, body.description)


@router.get("", response_model=list[Customer])
def list_customers(conn: sqlite3.Connection = Depends(get_db)) -> list[Customer]:
    return CustomersRepository(conn).list()


@router.get("/{customer_id}", response_model=Customer)
def get_customer(customer_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Customer:
    customer = CustomersRepository(conn).get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer


@router.patch("/{customer_id}", response_model=Customer)
def update_customer(
    customer_id: str, body: CustomerUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> Customer:
    fields = body.model_dump(exclude_unset=True)
    updated = CustomersRepository(conn).update(customer_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return updated


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: str, conn: sqlite3.Connection = Depends(get_db)) -> None:
    CustomersRepository(conn).delete(customer_id)
