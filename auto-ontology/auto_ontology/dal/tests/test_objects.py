# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The object layer on Postgres: catalog reads, confirmation, question context.

Built on a catalog of its own (customers, orders, a foreign key between them)
and never calls whole-catalog generation, which would propose types for every
table in the store the tests run against.

Needs a migrated database and skips without one.
"""

from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import select  # noqa: E402

from auto_ontology.dal import objects as dal  # noqa: E402
from auto_ontology.dal import schema as s  # noqa: E402
from auto_ontology.dal.session import store  # noqa: E402
from auto_ontology.objects import generate as gen  # noqa: E402
from auto_ontology.objects import service  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def require_schema():
    if not os.environ.get("POSTGRES_USER"):
        pytest.skip("POSTGRES_* not set")
    try:
        store().query_read("SELECT 1 FROM link_type LIMIT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"auto_ontology schema unavailable (alembic upgrade head): {exc}")


def _add(table, **values) -> str:
    return store().query_write(table.insert().values(**values).returning(table.c.id))[
        0
    ]["id"]


class Shop:
    def __init__(self, prefix: str) -> None:
        self.database = _add(s.catalog_database, name=prefix)
        schema = _add(s.catalog_schema, database_id=self.database, name="shop")
        self.customers = _add(
            s.catalog_table, schema_id=schema, name="customers", pk=["customer_id"]
        )
        self.orders = _add(
            s.catalog_table, schema_id=schema, name="orders", pk=["order_id"]
        )
        customer_id = _add(
            s.catalog_column,
            table_id=self.customers,
            name="customer_id",
            description="客户ID，主键",
            ordinal_position=1,
        )
        _add(
            s.catalog_column,
            table_id=self.customers,
            name="customer_name",
            ordinal_position=2,
        )
        _add(
            s.catalog_column, table_id=self.orders, name="order_id", ordinal_position=1
        )
        order_customer = _add(
            s.catalog_column,
            table_id=self.orders,
            name="customer_id",
            ordinal_position=2,
        )
        store().query_write(
            s.column__foreign_key.insert().values(
                source_column_id=order_customer, target_column_id=customer_id
            )
        )


@pytest.fixture
def shop():
    prefix = f"o-{uuid.uuid4().hex[:8]}"
    yield Shop(prefix)
    store().query_write(
        s.catalog_database.delete().where(s.catalog_database.c.name == prefix)
    )


def _propose(shop: Shop) -> dict[str, str]:
    """Generation's own rules, run on this test's tables only."""
    tables = dal.fetch_catalog_tables([shop.customers, shop.orders])
    specs, keyless = gen.type_candidates(tables, set())
    assert keyless == []
    dal.create_object_types(specs, created_by="tester")
    types = {
        t["table_id"]: t
        for t in dal.list_object_types()
        if t["table_id"] in (shop.customers, shop.orders)
    }
    pairs = [
        p
        for p in dal.fetch_key_pairs()
        if p["source_table_id"] in types and p["target_table_id"] in types
    ]
    links = gen.link_candidates(
        types, pairs, dal.link_keys(), {t["id"]: t["columns"] for t in tables}
    )
    dal.create_link_types(links, created_by="tester")
    return {
        "customers": types[shop.customers]["id"],
        "orders": types[shop.orders]["id"],
    }


def test_catalog_tables_come_with_location_and_ordered_columns(shop) -> None:
    (customers,) = dal.fetch_catalog_tables([shop.customers])
    assert customers["schema_name"] == "shop"
    assert customers["pk"] == ["customer_id"]
    assert [c["name"] for c in customers["columns"]] == ["customer_id", "customer_name"]


def test_proposals_are_candidates_named_from_the_catalog(shop) -> None:
    ids = _propose(shop)
    customer = dal.get_object_type(ids["customers"])
    assert customer["status"] == s.OBJECT_CANDIDATE
    assert customer["display_name"] == "客户"
    assert customer["title_column"] == "customer_name"
    (link,) = dal.list_link_types(type_id=ids["orders"])
    assert (link["source_column"], link["target_column"]) == (
        "customer_id",
        "customer_id",
    )
    assert (link["display_name"], link["reverse_display_name"]) == ("客户", "orders")
    assert link["status"] == s.OBJECT_CANDIDATE


def test_proposing_twice_creates_nothing_new(shop) -> None:
    ids = _propose(shop)
    before = dal.list_link_types(type_id=ids["orders"])
    again = _propose(shop)
    assert again == ids
    assert dal.list_link_types(type_id=ids["orders"]) == before


def test_accepting_both_ends_confirms_the_link_between_them(shop) -> None:
    ids = _propose(shop)
    service.accept([ids["customers"]], modified_by="tester")
    (link,) = dal.list_link_types(type_id=ids["orders"])
    assert link["status"] == s.OBJECT_CANDIDATE  # orders is not confirmed yet

    result = service.accept([ids["orders"]], modified_by="tester")
    assert result == {"types": 1, "links": 1}
    (link,) = dal.list_link_types(type_id=ids["orders"])
    assert link["status"] == s.OBJECT_ACTIVE


def test_question_context_reads_confirmed_objects_from_both_ends(shop) -> None:
    ids = _propose(shop)
    assert dal.fetch_object_context([shop.orders]) == {}  # nothing confirmed

    service.accept([ids["customers"], ids["orders"]], modified_by="tester")
    found = dal.fetch_object_context([shop.orders, shop.customers])

    assert found[shop.orders]["name"] == "orders"
    (out,) = found[shop.orders]["links"]
    assert (out["direction"], out["name"], out["other_table"]) == (
        "out",
        "客户",
        "customers",
    )
    (back,) = found[shop.customers]["links"]
    assert (back["direction"], back["column"], back["other_column"]) == (
        "in",
        "customer_id",
        "customer_id",
    )


def test_property_overrides_are_replaced_whole(shop) -> None:
    ids = _propose(shop)
    dal.update_object_type(
        ids["customers"],
        {"display_name": "会员"},
        properties=[
            {"column_name": "customer_name", "display_name": "姓名", "hidden": False},
            {"column_name": "customer_id", "display_name": "", "hidden": False},
        ],
        modified_by="tester",
    )
    assert dal.fetch_property_overrides(ids["customers"]) == {
        "customer_name": {
            "column_name": "customer_name",
            "display_name": "姓名",
            "hidden": False,
        }
    }
    assert dal.get_object_type(ids["customers"])["display_name"] == "会员"


def test_deleting_a_table_takes_its_object_and_links(shop) -> None:
    ids = _propose(shop)
    store().query_write(
        s.catalog_table.delete().where(s.catalog_table.c.id == shop.customers)
    )
    assert dal.get_object_type(ids["customers"]) is None
    assert (
        store().query_read(
            select(s.link_type.c.id).where(
                s.link_type.c.target_object_type_id == ids["customers"]
            )
        )
        == []
    )
