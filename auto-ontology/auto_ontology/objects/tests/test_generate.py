# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Candidate generation: which tables become types, and how links are named."""

from __future__ import annotations

from typing import Any

from auto_ontology.objects import generate as gen


def _table(
    table_id: str,
    name: str,
    *,
    pk: list[str] | None = None,
    columns: list[str] | None = None,
    description: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": table_id,
        "name": name,
        "description": description,
        "pk": pk or [],
        "columns": [{"name": c, "description": None} for c in columns or []],
        **extra,
    }


def test_short_label_takes_the_first_clause_and_drops_the_table_suffix() -> None:
    assert gen.short_label("客户信息表，记录所有注册客户", "customers") == "客户信息"
    assert gen.short_label("订单表", "orders") == "订单"
    assert gen.short_label(None, "orders") == "orders"
    sentence = "This table stores one row for every order placed through the shop"
    assert gen.short_label(sentence, "orders") == "orders"


def test_type_label_strips_warehouse_layer_prefixes() -> None:
    assert gen.type_label(_table("t", "dim_customer")) == "customer"
    assert (
        gen.type_label(_table("t", "dim_customer", description="客户维表")) == "客户维"
    )


def test_type_label_falls_back_to_what_the_key_describes() -> None:
    table = _table("t", "order_items", pk=["order_item_id"])
    table["columns"] = [{"name": "order_item_id", "description": "订单明细ID，主键"}]
    assert gen.type_label(table, "order_item_id") == "订单明细"
    table["description"] = "订单行"
    assert gen.type_label(table, "order_item_id") == "订单行"


def test_key_column_prefers_a_declared_single_key() -> None:
    assert (
        gen.key_column(_table("t", "orders", pk=["order_no"], columns=["id"]))
        == "order_no"
    )


def test_key_column_refuses_a_composite_key() -> None:
    assert gen.key_column(_table("t", "order_items", pk=["order_id", "line"])) is None


def test_key_column_guesses_from_names_when_nothing_is_declared() -> None:
    assert gen.key_column(_table("t", "orders", columns=["ID", "amount"])) == "ID"
    assert (
        gen.key_column(_table("t", "customers", columns=["customer_id"]))
        == "customer_id"
    )
    assert gen.key_column(_table("t", "dim_shop", columns=["shop_id"])) == "shop_id"
    assert gen.key_column(_table("t", "events", columns=["ts", "kind"])) is None


def test_title_column_finds_a_name_by_column_name_or_description() -> None:
    columns = [
        {"name": "id", "description": None},
        {"name": "customer_name", "description": None},
    ]
    assert gen.title_column(columns, "id") == "customer_name"
    columns = [
        {"name": "id", "description": None},
        {"name": "khmc", "description": "客户名称"},
    ]
    assert gen.title_column(columns, "id") == "khmc"
    assert gen.title_column([{"name": "id", "description": None}], "id") is None


def test_type_candidates_skip_views_keyless_and_taken_tables() -> None:
    tables = [
        _table("1", "customers", pk=["id"]),
        _table("2", "v_sales", pk=["id"], table_type="VIEW"),
        _table("3", "order_items", pk=["id"], is_junction_table=True),
        _table("4", "orders", pk=["id"]),
        _table("5", "logs", columns=["ts"]),
        _table("6", "order_tags", pk=["order_id", "tag_id"], is_junction_table=True),
    ]
    specs, keyless = gen.type_candidates(tables, taken_table_ids={"4"})
    # A junction with its own key is a thing (an order line); one keyed by
    # the pair it joins is not.
    assert [spec["table_id"] for spec in specs] == ["1", "3"]
    assert keyless == ["logs", "order_tags"]


def _types() -> dict[str, dict[str, Any]]:
    return {
        "t_order": {"id": "order", "display_name": "订单"},
        "t_user": {"id": "user", "display_name": "用户"},
        "t_category": {"id": "category", "display_name": "类目"},
    }


def _pair(
    src: str, col: str, tgt: str, tcol: str = "id", origin: str = "foreign_key"
) -> dict:
    return {
        "source_table_id": src,
        "source_column": col,
        "target_table_id": tgt,
        "target_column": tcol,
        "origin": origin,
    }


def test_links_are_named_after_the_types_they_join() -> None:
    specs = gen.link_candidates(
        _types(), [_pair("t_order", "user_id", "t_user")], set(), {}
    )
    assert specs == [
        {
            "object_type_id": "order",
            "target_object_type_id": "user",
            "source_column": "user_id",
            "target_column": "id",
            "display_name": "用户",
            "reverse_display_name": "订单",
            "origin": "foreign_key",
        }
    ]


def test_two_links_between_the_same_types_are_told_apart_by_column() -> None:
    columns = {
        "t_order": [
            {"name": "buyer_id", "description": "买家，下单用户"},
            {"name": "seller_id", "description": None},
        ]
    }
    specs = gen.link_candidates(
        _types(),
        [
            _pair("t_order", "buyer_id", "t_user"),
            _pair("t_order", "seller_id", "t_user"),
        ],
        set(),
        columns,
    )
    assert [(s["display_name"], s["reverse_display_name"]) for s in specs] == [
        ("用户（买家）", "订单（买家）"),
        ("用户（seller_id）", "订单（seller_id）"),
    ]


def test_existing_links_and_duplicate_pairs_are_not_proposed_again() -> None:
    pairs = [
        _pair("t_order", "user_id", "t_user"),
        _pair("t_order", "user_id", "t_user", origin="semantic_fk"),
        _pair("t_order", "shop_id", "t_shop"),  # no type for the target
    ]
    assert len(gen.link_candidates(_types(), pairs, set(), {})) == 1
    assert (
        gen.link_candidates(_types(), pairs, {("order", "user_id", "user")}, {}) == []
    )


def test_a_self_link_is_kept_but_a_column_onto_itself_is_not() -> None:
    pairs = [
        _pair("t_category", "parent_id", "t_category"),
        _pair("t_category", "id", "t_category"),
    ]
    specs = gen.link_candidates(_types(), pairs, set(), {})
    assert [s["source_column"] for s in specs] == ["parent_id"]
