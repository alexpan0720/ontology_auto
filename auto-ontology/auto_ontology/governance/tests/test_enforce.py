# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pandas as pd
import pytest

from auto_ontology.governance.enforce import (
    DECISION_ALLOWED,
    DECISION_BLOCKED,
    DECISION_FILTERED,
    AccessContext,
    AccessDeniedError,
    ColumnRule,
    MaskRule,
    PolicyEnforcingConnector,
    RowRule,
    detect_mask_style,
    enforce_sql,
    hide_restricted_columns,
    summarize,
    validate_predicate,
    wrap_connectors,
)

DB, SCHEMA = "workspace", "demo_shop"
DIALECT = "databricks"

PHONE = ColumnRule("p-col", DB, SCHEMA, "customers", "phone")
EAST = RowRule(("p-row",), DB, SCHEMA, "orders", "province IN ('浙江', '江苏', '上海')")
NO_ROWS = RowRule(("p-none",), DB, SCHEMA, "orders", None)


def ctx(**kwargs: Any) -> AccessContext:
    return AccessContext(**kwargs)


class TestColumns:
    def test_restricted_column_in_select_is_blocked(self) -> None:
        result = enforce_sql(
            "SELECT customer_name, phone FROM workspace.demo_shop.customers",
            DIALECT,
            ctx(columns=[PHONE]),
        )
        assert result.decision == DECISION_BLOCKED
        assert "customers.phone" in result.reason
        assert result.policy_ids == ["p-col"]

    def test_restricted_column_in_filter_is_blocked(self) -> None:
        result = enforce_sql(
            "SELECT customer_name FROM demo_shop.customers WHERE phone LIKE '138%'",
            DIALECT,
            ctx(columns=[PHONE]),
        )
        assert result.decision == DECISION_BLOCKED

    def test_star_over_restricted_table_is_blocked(self) -> None:
        result = enforce_sql("SELECT * FROM customers", DIALECT, ctx(columns=[PHONE]))
        assert result.decision == DECISION_BLOCKED
        assert "*" in result.reason

    def test_count_star_is_not_a_projection(self) -> None:
        result = enforce_sql(
            "SELECT COUNT(*) FROM customers", DIALECT, ctx(columns=[PHONE])
        )
        assert result.decision == DECISION_ALLOWED

    def test_other_columns_of_restricted_table_are_allowed(self) -> None:
        result = enforce_sql(
            "SELECT city, COUNT(*) FROM demo_shop.customers GROUP BY city",
            DIALECT,
            ctx(columns=[PHONE]),
        )
        assert result.decision == DECISION_ALLOWED

    def test_rule_for_untouched_table_does_not_apply(self) -> None:
        result = enforce_sql(
            "SELECT phone FROM demo_shop.suppliers", DIALECT, ctx(columns=[PHONE])
        )
        assert result.decision == DECISION_ALLOWED

    def test_other_schema_with_same_table_name_does_not_match(self) -> None:
        result = enforce_sql(
            "SELECT phone FROM crm.customers", DIALECT, ctx(columns=[PHONE])
        )
        assert result.decision == DECISION_ALLOWED


class TestRows:
    def test_table_is_replaced_by_filtered_subquery(self) -> None:
        result = enforce_sql(
            "SELECT o.channel, COUNT(*) FROM workspace.demo_shop.orders AS o "
            "GROUP BY o.channel",
            DIALECT,
            ctx(rows=[EAST]),
        )
        assert result.decision == DECISION_FILTERED
        assert result.policy_ids == ["p-row"]
        sql = result.sql
        assert "WHERE province IN ('浙江', '江苏', '上海')" in sql
        assert ") AS o" in sql
        assert "o.channel" in sql

    def test_unaliased_reference_keeps_its_name(self) -> None:
        result = enforce_sql(
            "SELECT orders.status FROM orders", DIALECT, ctx(rows=[EAST])
        )
        assert result.decision == DECISION_FILTERED
        assert ") AS orders" in result.sql

    def test_every_reference_is_filtered(self) -> None:
        result = enforce_sql(
            "SELECT a.order_id FROM orders a JOIN orders b ON a.order_id = b.order_id",
            DIALECT,
            ctx(rows=[EAST]),
        )
        assert result.sql.count("WHERE province IN") == 2

    def test_no_applicable_policy_means_no_rows(self) -> None:
        result = enforce_sql(
            "SELECT COUNT(*) FROM orders", DIALECT, ctx(rows=[NO_ROWS])
        )
        assert result.decision == DECISION_FILTERED
        assert "WHERE FALSE" in result.sql.upper()

    def test_cte_with_same_name_is_not_a_table(self) -> None:
        result = enforce_sql(
            "WITH orders AS (SELECT 1 AS x) SELECT x FROM orders",
            DIALECT,
            ctx(rows=[EAST]),
        )
        assert result.decision == DECISION_ALLOWED


class TestFailClosed:
    def test_unparseable_sql_is_blocked(self) -> None:
        result = enforce_sql("SELEC phone FRM", DIALECT, ctx(columns=[PHONE]))
        assert result.decision == DECISION_BLOCKED

    def test_multiple_statements_are_blocked(self) -> None:
        result = enforce_sql("SELECT 1; SELECT 2", DIALECT, ctx(rows=[EAST]))
        assert result.decision == DECISION_BLOCKED

    def test_admin_is_unrestricted(self) -> None:
        result = enforce_sql(
            "SELECT * FROM customers", DIALECT, ctx(is_admin=True, columns=[PHONE])
        )
        assert result.decision == DECISION_ALLOWED
        assert result.sql == "SELECT * FROM customers"


def test_predicate_validation() -> None:
    assert validate_predicate("province = '浙江'") is None
    assert validate_predicate("SELECT 1") is not None
    assert validate_predicate("id IN (SELECT id FROM x)") is not None
    assert validate_predicate("province = ") is not None


def test_hide_restricted_columns() -> None:
    tables = [
        {
            "name": "customers",
            "schema_name": SCHEMA,
            "database_name": DB,
            "columns": [{"name": "city"}, {"name": "PHONE"}],
        },
        {
            "name": "orders",
            "schema_name": SCHEMA,
            "database_name": DB,
            "columns": [{"name": "phone"}],
        },
    ]
    hidden = hide_restricted_columns(tables, ctx(columns=[PHONE]))
    assert [c["name"] for c in hidden[0]["columns"]] == ["city"]
    assert [c["name"] for c in hidden[1]["columns"]] == ["phone"]
    assert [c["name"] for c in tables[0]["columns"]] == ["city", "PHONE"]


def test_context_round_trips_through_dict() -> None:
    original = ctx(columns=[PHONE], rows=[EAST, NO_ROWS])
    assert AccessContext.from_dict(original.to_dict()) == original


class FakeConnector:
    dialect = DIALECT
    database_name = DB
    supports_statement_timeout = True

    def __init__(self) -> None:
        self.ran: list[str] = []

    def execute(self, sql: str, parameters: Any = None, **kwargs: Any) -> pd.DataFrame:
        self.ran.append(sql)
        return pd.DataFrame([{"n": 1}])


class TestConnector:
    def test_blocked_statement_never_reaches_database(self) -> None:
        inner, log = FakeConnector(), []
        wrapped = PolicyEnforcingConnector(inner, ctx(columns=[PHONE]), log)  # type: ignore[arg-type]
        with pytest.raises(AccessDeniedError):
            wrapped.execute("SELECT phone FROM customers")
        assert inner.ran == []
        assert log[0]["decision"] == DECISION_BLOCKED
        assert log[0]["executed_sql"] is None

    def test_rewritten_statement_is_what_runs(self) -> None:
        inner, log = FakeConnector(), []
        wrapped = PolicyEnforcingConnector(inner, ctx(rows=[EAST]), log)  # type: ignore[arg-type]
        wrapped.execute("SELECT COUNT(*) FROM orders", timeout_s=5)
        assert "WHERE province IN" in inner.ran[0]
        assert log[0]["executed_sql"] == inner.ran[0]
        assert wrapped.supports_statement_timeout is True

    def test_rules_for_another_database_do_not_apply(self) -> None:
        inner, log = FakeConnector(), []
        other = ColumnRule("p", "other_db", SCHEMA, "customers", "phone")
        wrapped = PolicyEnforcingConnector(inner, ctx(columns=[other]), log)  # type: ignore[arg-type]
        wrapped.execute("SELECT phone FROM customers")
        assert inner.ran == ["SELECT phone FROM customers"]

    def test_admin_statements_run_unchanged_but_are_logged(self) -> None:
        inner, log = FakeConnector(), []
        [wrapped] = wrap_connectors([inner], ctx(is_admin=True, columns=[PHONE]), log)  # type: ignore[list-item]
        wrapped.execute("SELECT * FROM customers")
        assert inner.ran == ["SELECT * FROM customers"]
        assert log[0]["decision"] == DECISION_ALLOWED


def test_summarize_takes_the_strictest_decision() -> None:
    log = [
        {"decision": DECISION_FILTERED, "reason": "", "policy_ids": ["p-row"]},
        {"decision": DECISION_BLOCKED, "reason": "无权限", "policy_ids": ["p-col"]},
    ]
    summary = summarize(log)
    assert summary["decision"] == DECISION_BLOCKED
    assert summary["reason"] == "无权限"
    assert summary["policy_ids"] == ["p-col", "p-row"]


CUSTOMER_COLUMNS = ("customer_id", "customer_name", "phone", "city")
NAME_MASK = MaskRule(
    "p-mask", DB, SCHEMA, "customers", "customer_name", "name", CUSTOMER_COLUMNS
)
PHONE_MASK = MaskRule(
    "p-phone", DB, SCHEMA, "customers", "phone", "phone", CUSTOMER_COLUMNS
)


class TestMasks:
    def test_masked_column_is_read_through_a_masking_subquery(self) -> None:
        result = enforce_sql(
            "SELECT c.customer_name, c.city FROM workspace.demo_shop.customers c",
            DIALECT,
            ctx(masks=[NAME_MASK]),
        )
        assert result.decision == DECISION_FILTERED
        assert result.policy_ids == ["p-mask"]
        sql = result.sql
        assert "AS `customer_name`" in sql
        assert "SUBSTRING(CAST(`customer_name` AS STRING), 1, 1)" in sql
        assert "`city`" in sql and ") AS c" in sql

    def test_star_is_allowed_because_every_column_is_projected(self) -> None:
        result = enforce_sql("SELECT * FROM customers", DIALECT, ctx(masks=[NAME_MASK]))
        assert result.decision == DECISION_FILTERED
        assert "`customer_id`" in result.sql and "`phone`" in result.sql

    def test_several_masks_share_one_subquery(self) -> None:
        result = enforce_sql(
            "SELECT phone, customer_name FROM customers",
            DIALECT,
            ctx(masks=[NAME_MASK, PHONE_MASK]),
        )
        assert result.sql.count("FROM customers") == 1
        assert "'****'" in result.sql
        assert result.policy_ids == ["p-mask", "p-phone"]

    def test_mask_and_row_policy_combine(self) -> None:
        rows = RowRule(("p-row",), DB, SCHEMA, "customers", "city = '杭州'")
        result = enforce_sql(
            "SELECT customer_name FROM customers",
            DIALECT,
            ctx(masks=[NAME_MASK], rows=[rows]),
        )
        assert result.sql.count("SELECT") == 2
        assert "WHERE city = '杭州'" in result.sql
        assert result.policy_ids == ["p-mask", "p-row"]

    def test_unknown_columns_are_refused(self) -> None:
        blind = MaskRule("p-x", DB, SCHEMA, "customers", "phone", "phone", ())
        result = enforce_sql("SELECT city FROM customers", DIALECT, ctx(masks=[blind]))
        assert result.decision == DECISION_BLOCKED

    def test_postgres_renders_its_own_concatenation(self) -> None:
        result = enforce_sql(
            "SELECT phone FROM demo_shop.customers", "postgres", ctx(masks=[PHONE_MASK])
        )
        assert "||" in result.sql and "SUBSTRING(" in result.sql

    def test_admin_sees_real_values(self) -> None:
        result = enforce_sql(
            "SELECT customer_name FROM customers",
            DIALECT,
            ctx(is_admin=True, masks=[NAME_MASK]),
        )
        assert result.decision == DECISION_ALLOWED


@pytest.mark.parametrize(
    ("column", "style"),
    [
        ("customer_name", "name"),
        ("contact_phone", "phone"),
        ("mobile", "phone"),
        ("email", "email"),
        ("id_card_no", "id_number"),
        ("home_address", "address"),
        ("手机号", "phone"),
        ("city", "partial"),
    ],
)
def test_detect_mask_style(column: str, style: str) -> None:
    assert detect_mask_style(column) == style


def test_context_with_masks_round_trips() -> None:
    original = ctx(masks=[NAME_MASK, PHONE_MASK])
    assert AccessContext.from_dict(original.to_dict()) == original
