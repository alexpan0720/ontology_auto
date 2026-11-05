# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Business objects as question context, and how a prompt shows them."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from auto_ontology.objects import context
from auto_ontology.retrieval.text_to_sql.formatters_util import (
    format_tables_for_prompt,
    format_used_schema_for_prompt,
)

ORDER_CONTEXT = {
    "name": "订单",
    "description": "一次下单",
    "links": [
        {
            "direction": "out",
            "name": "下单客户",
            "column": "customer_id",
            "other_object": "客户",
            "other_table_id": "t_customers",
            "other_table": "customers",
            "other_schema": "shop",
            "other_column": "customer_id",
        },
        {
            "direction": "in",
            "name": "订单明细",
            "column": "order_id",
            "other_object": "订单明细",
            "other_table_id": "t_items",
            "other_table": "order_items",
            "other_schema": "shop",
            "other_column": "order_id",
        },
    ],
}


def _table(table_id: str, name: str, columns: list[str], **extra: Any) -> dict:
    return {
        "id": table_id,
        "name": name,
        "schema_name": "shop",
        "database_name": "db",
        "columns": [{"name": c, "data_type": "bigint"} for c in columns],
        **extra,
    }


def test_annotation_marks_only_tables_with_an_object() -> None:
    tables = [_table("t_orders", "orders", []), _table("t_logs", "logs", [])]
    with patch.object(
        context.dal, "fetch_object_context", return_value={"t_orders": ORDER_CONTEXT}
    ) as fetch:
        annotated = context.annotate_business_objects(tables)
    fetch.assert_called_once_with(["t_orders", "t_logs"])
    assert annotated[0][context.BUSINESS_OBJECT] == ORDER_CONTEXT
    assert annotated[1][context.BUSINESS_OBJECT] is None


def test_annotation_reads_only_tables_not_yet_annotated() -> None:
    done = {**_table("t_orders", "orders", []), context.BUSINESS_OBJECT: ORDER_CONTEXT}
    fresh = _table("t_customers", "customers", [])
    with patch.object(context.dal, "fetch_object_context", return_value={}) as fetch:
        annotated = context.annotate_business_objects([done, fresh])
    fetch.assert_called_once_with(["t_customers"])
    assert annotated[0] is done


def test_a_failed_read_leaves_the_question_alone() -> None:
    tables = [_table("t_orders", "orders", [])]
    with patch.object(
        context.dal, "fetch_object_context", side_effect=RuntimeError("db down")
    ):
        assert context.annotate_business_objects(tables) == tables


def test_the_prompt_names_the_object_and_its_links_as_joins() -> None:
    orders = _table(
        "t_orders",
        "orders",
        ["order_id", "customer_id"],
        business_object=ORDER_CONTEXT,
    )
    customers = _table("t_customers", "customers", ["customer_id"])
    text = format_tables_for_prompt([orders, customers], dialect="postgres")

    assert "Business object: 订单 — 一次下单" in text
    assert (
        '- link "下单客户" (客户, one per 订单): '
        "db.shop.orders.customer_id = db.shop.customers.customer_id"
    ) in text
    # order_items is not among the tables given to the model, so the link to
    # it is not shown.
    assert "订单明细" not in text


def test_a_link_through_a_withheld_column_is_not_shown() -> None:
    orders = _table("t_orders", "orders", ["order_id"], business_object=ORDER_CONTEXT)
    customers = _table("t_customers", "customers", ["customer_id"])
    text = format_tables_for_prompt([orders, customers], dialect="postgres")
    assert "Business object: 订单" in text
    assert "customer_id =" not in text


def test_tables_without_an_object_render_as_before() -> None:
    plain = _table("t_logs", "logs", ["ts"])
    annotated = {**plain, "business_object": None}
    assert format_tables_for_prompt([annotated]) == format_tables_for_prompt([plain])


def test_the_used_schema_names_the_object() -> None:
    orders = _table("t_orders", "orders", ["order_id"], business_object=ORDER_CONTEXT)
    text = format_used_schema_for_prompt([orders], ["shop.orders"], [])
    assert "| business object: 订单" in text
