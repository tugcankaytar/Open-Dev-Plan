from __future__ import annotations

from odp.repositories.customers import CustomersRepository
from odp.repositories.projects import ProjectsRepository


def test_create_and_get_customer(db_conn):
    repo = CustomersRepository(db_conn)
    customer = repo.create("Acme A.Ş.", "Uzun süreli müşteri")

    fetched = repo.get(customer.id)
    assert fetched is not None
    assert fetched.name == "Acme A.Ş."
    assert fetched.description == "Uzun süreli müşteri"


def test_list_orders_by_name(db_conn):
    repo = CustomersRepository(db_conn)
    repo.create("Zeta Ltd.")
    repo.create("Acme A.Ş.")

    names = [c.name for c in repo.list()]
    assert names == ["Acme A.Ş.", "Zeta Ltd."]


def test_update_customer(db_conn):
    repo = CustomersRepository(db_conn)
    customer = repo.create("Eski İsim")

    updated = repo.update(customer.id, name="Yeni İsim")
    assert updated is not None
    assert updated.name == "Yeni İsim"


def test_delete_customer(db_conn):
    repo = CustomersRepository(db_conn)
    customer = repo.create("Silinecek")
    repo.delete(customer.id)
    assert repo.get(customer.id) is None


def test_project_can_be_linked_to_customer(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    customer = customers_repo.create("Acme A.Ş.")
    project = projects_repo.create("Web Sitesi Yenileme", customer_ids=[customer.id])

    fetched = projects_repo.get(project.id)
    assert fetched is not None
    assert fetched.customer_ids == [customer.id]


def test_project_can_be_linked_to_multiple_customers(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    c1 = customers_repo.create("Müşteri 1")
    c2 = customers_repo.create("Müşteri 2")
    project = projects_repo.create("Ortak Proje", customer_ids=[c1.id, c2.id])

    fetched = projects_repo.get(project.id)
    assert fetched is not None
    assert set(fetched.customer_ids) == {c1.id, c2.id}


def test_deleting_customer_unlinks_project(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    customer = customers_repo.create("Acme A.Ş.")
    project = projects_repo.create("Proje", customer_ids=[customer.id])

    customers_repo.delete(customer.id)

    fetched = projects_repo.get(project.id)
    assert fetched is not None
    assert fetched.customer_ids == []  # ON DELETE CASCADE on the join row


def test_deleting_one_customer_keeps_other_links(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    c1 = customers_repo.create("Müşteri 1")
    c2 = customers_repo.create("Müşteri 2")
    project = projects_repo.create("Ortak Proje", customer_ids=[c1.id, c2.id])

    customers_repo.delete(c1.id)

    fetched = projects_repo.get(project.id)
    assert fetched is not None
    assert fetched.customer_ids == [c2.id]


def test_list_projects_filtered_by_customer(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    c1 = customers_repo.create("Müşteri 1")
    c2 = customers_repo.create("Müşteri 2")
    projects_repo.create("P1", customer_ids=[c1.id])
    projects_repo.create("P2", customer_ids=[c2.id])
    projects_repo.create("Dahili proje")  # no customer

    assert [p.name for p in projects_repo.list(customer_id=c1.id)] == ["P1"]
    assert len(projects_repo.list()) == 3


def test_update_can_clear_customer_ids_explicitly(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    customer = customers_repo.create("Müşteri")
    project = projects_repo.create("Proje", customer_ids=[customer.id])

    updated = projects_repo.update(project.id, customer_ids=[])
    assert updated is not None
    assert updated.customer_ids == []


def test_update_without_customer_ids_keeps_existing_value(db_conn):
    customers_repo = CustomersRepository(db_conn)
    projects_repo = ProjectsRepository(db_conn)

    customer = customers_repo.create("Müşteri")
    project = projects_repo.create("Proje", customer_ids=[customer.id])

    updated = projects_repo.update(project.id, name="Yeni Ad")  # customer_ids not passed
    assert updated is not None
    assert updated.customer_ids == [customer.id]
