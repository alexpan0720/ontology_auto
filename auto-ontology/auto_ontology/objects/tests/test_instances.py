# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Instance reads: the SQL they build, and what a caller's policies take out."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from auto_ontology.governance.enforce import AccessContext, ColumnRule
from auto_ontology.objects import instances
from auto_ontology.subscriptions.service import QueryResult, RunError


def test_literals_follow_the_column_type() -> None:
    assert instances.literal("42", "bigint").sql() == "42"
    assert instances.literal("42", "varchar(20)").sql() == "'42'"
    assert instances.literal(42, "text").sql() == "'42'"
    assert instances.literal(42.0, None).sql() == "42"
    assert instances.literal("A-1", "integer").sql() == "'A-1'"
    assert (
        instances.literal("x'; drop table t; --", None).sql()
        == "'x''; drop table t; --'"
    )


def test_build_select_quotes_names_and_respects_dialect_paging() -> None:
    where = instances.search_condition(["id", "name"], "Ab")
    sql = instances.build_select(
        '"cat"."sales"."orders"',
        ["id", "name"],
        "trino",
        where=where,
        order_by="id",
        limit=21,
        offset=20,
    )
    assert sql == (
        'SELECT "id", "name" FROM "cat"."sales"."orders" WHERE '
        "LOWER(CAST(\"id\" AS VARCHAR)) LIKE '%ab%' OR "
        "LOWER(CAST(\"name\" AS VARCHAR)) LIKE '%ab%' "
        'ORDER BY "id" OFFSET 20 LIMIT 21'
    )


def _view(
    restricted: set[str] | None = None, title: str | None = "name"
) -> instances.TypeView:
    return instances.TypeView(
        type={
            "id": "customer",
            "display_name": "客户",
            "pk_column": "id",
            "title_column": title,
            "status": "active",
        },
        table={
            "name": "customers",
            "schema_name": "public",
            "database_name": "shop",
        },
        properties=[
            {"column_name": "id", "hidden": False, "data_type": "integer"},
            {"column_name": "name", "hidden": False, "data_type": "text"},
            {"column_name": "phone", "hidden": False, "data_type": "text"},
            {"column_name": "internal", "hidden": True, "data_type": "text"},
        ],
        restricted=restricted or set(),
    )


def test_shown_columns_leave_out_hidden_and_restricted_ones() -> None:
    assert _view().shown_columns() == ["id", "name", "phone"]
    assert _view({"phone"}).shown_columns() == ["id", "name"]


def test_a_restricted_title_falls_back_to_the_key() -> None:
    view = _view({"name"})
    assert view.title == "id"
    assert view.shown_columns() == ["id", "phone"]


class _Connector:
    database_name = "shop"
    dialect = "postgres"

    def qualify(self, schema: str, table: str) -> str:
        return f'"{schema}"."{table}"'


def _reader(subject_token: str | None = None) -> instances.Reader:
    return instances.Reader(
        user_id="u1", access=AccessContext(), subject_token=subject_token
    )


def _run_with(rows: list[dict[str, Any]]):
    calls: list[dict[str, Any]] = []

    def fake_run(
        sql: str, database: str, user: str | None, label: str, **kwargs: Any
    ) -> QueryResult:
        calls.append({"sql": sql, "user": user, **kwargs})
        return QueryResult(rows=rows, columns=list(rows[0]) if rows else [])

    return calls, fake_run


def test_list_objects_pages_by_key_and_reports_more() -> None:
    rows = [{"id": i, "name": f"c{i}", "phone": "1"} for i in range(3)]
    calls, fake_run = _run_with(rows)
    with (
        patch("auto_ontology.connectors.get_connectors", return_value=[_Connector()]),
        patch("auto_ontology.subscriptions.service.run_query", fake_run),
    ):
        page = instances.list_objects(_view(), _reader(), search="c", limit=2)
    assert calls[0]["sql"].endswith('ORDER BY "id" LIMIT 3')
    assert "LIKE '%c%'" in calls[0]["sql"]
    assert [o["key"] for o in page["objects"]] == ["0", "1"]
    assert page["objects"][0]["title"] == "c0"
    assert page["has_more"] is True


def test_a_restricted_key_refuses_before_querying() -> None:
    with pytest.raises(instances.ObjectQueryError):
        instances.list_objects(_view({"id"}), _reader())


def test_query_errors_reach_the_caller_as_object_errors() -> None:
    def failing(*_: Any, **__: Any) -> QueryResult:
        raise RunError("查询失败：boom")

    with (
        patch("auto_ontology.connectors.get_connectors", return_value=[_Connector()]),
        patch("auto_ontology.subscriptions.service.run_query", failing),
        pytest.raises(instances.ObjectQueryError, match="boom"),
    ):
        instances.list_objects(_view(), _reader())


def test_statements_run_as_the_reader_through_one_connector_lookup() -> None:
    """The caller's policies and connector are resolved once per request."""
    rows = [{"id": 1, "name": "c1", "phone": "1"}]
    calls, fake_run = _run_with(rows)
    reader = _reader()
    connector = _Connector()
    with (
        patch(
            "auto_ontology.connectors.get_connectors", return_value=[connector]
        ) as get_connectors,
        patch("auto_ontology.subscriptions.service.run_query", fake_run),
    ):
        instances.list_objects(_view(), reader)
        instances.list_objects(_view(), reader, offset=50)
    assert get_connectors.call_count == 1
    assert all(c["connector"] is connector for c in calls)
    assert all(c["access"] is reader.access and c["user"] == "u1" for c in calls)


def test_a_signed_in_reader_reads_through_their_own_connectors() -> None:
    rows = [{"id": 1, "name": "c1", "phone": "1"}]
    calls, fake_run = _run_with(rows)
    own = _Connector()
    with (
        patch(
            "auto_ontology.connectors.registry.get_connectors_for_subject_token",
            return_value=[own],
        ) as for_token,
        patch("auto_ontology.connectors.get_connectors") as shared,
        patch("auto_ontology.subscriptions.service.run_query", fake_run),
    ):
        instances.list_objects(_view(), _reader("sso-jwt"))
    for_token.assert_called_once_with("sso-jwt")
    shared.assert_not_called()
    assert calls[0]["connector"] is own


def test_a_refused_token_exchange_is_an_object_error() -> None:
    from auto_ontology.connectors.databricks_oauth import DatabricksOAuthError

    with (
        patch(
            "auto_ontology.connectors.registry.get_connectors_for_subject_token",
            side_effect=DatabricksOAuthError("token rejected"),
        ),
        pytest.raises(instances.ObjectQueryError, match="token rejected"),
    ):
        instances.list_objects(_view(), _reader("sso-jwt"))


def test_an_unknown_database_is_an_object_error() -> None:
    with (
        patch("auto_ontology.connectors.get_connectors", return_value=[]),
        pytest.raises(instances.ObjectQueryError, match="shop"),
    ):
        instances.list_objects(_view(), _reader())


def test_load_view_marks_columns_a_policy_withholds() -> None:
    table = {
        "id": "t1",
        "name": "customers",
        "schema_name": "public",
        "database_name": "shop",
        "columns": [
            {"name": "id", "description": None, "data_type": "integer"},
            {"name": "phone", "description": "手机号", "data_type": "text"},
        ],
    }
    object_type = {
        "id": "customer",
        "table_id": "t1",
        "display_name": "客户",
        "pk_column": "id",
        "title_column": None,
        "status": "active",
    }
    access = AccessContext(
        columns=[
            ColumnRule(
                policy_id="p",
                database="shop",
                schema="public",
                table="customers",
                column="PHONE",
            )
        ]
    )
    with (
        patch.object(instances.dal, "get_object_type", return_value=object_type),
        patch.object(instances.dal, "fetch_catalog_tables", return_value=[table]),
        patch.object(
            instances.dal,
            "fetch_property_overrides",
            return_value={"id": {"display_name": "编号", "hidden": False}},
        ),
    ):
        view = instances.load_view("customer", access)
    assert view is not None
    assert view.restricted == {"phone"}
    assert [p["label"] for p in view.properties] == ["编号", "手机号"]
    assert view.shown_columns() == ["id"]
