# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Read object instances from the source database, as the caller may see them.

Every statement goes through
:func:`auto_ontology.subscriptions.service.run_query`, so it passes the same
policy layer as a chat question — row policies filter the instances, masks hide
values — and lands in the access audit. A connection set to authenticate as the
signed-in user is reached with the caller's own exchanged token, as chat does,
so the source database's own grants apply too. Columns a column policy withholds are
left out of the select list beforehand rather than tripping the refusal: an
object page with one property missing is more use than no page at all. Only
the key cannot be dropped, since without it there is no instance to address.

The SQL is built with sqlglot from catalog names, never from caller text: the
search term and key values only ever enter as literals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlglot import exp

from auto_ontology.dal import objects as dal
from auto_ontology.dal import schema as s
from auto_ontology.objects.generate import short_label

#: Instances listed per linked type on an object page.
LINKED_LIMIT = 10
MAX_PAGE = 200

_NUMERIC_TYPE = re.compile(r"int|numeric|decimal|number|float|double|real")
_TEXT_TYPE = re.compile(r"char|text|string|clob")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")


class ObjectQueryError(RuntimeError):
    """The instances could not be read; the message is user-facing."""


@dataclass
class TypeView:
    """One object type, resolved against its table and the caller's policies."""

    type: dict[str, Any]
    table: dict[str, Any]
    #: Every column, in catalog order, with its label and whether it shows.
    properties: list[dict[str, Any]]
    #: Columns the caller's column policies withhold.
    restricted: set[str] = field(default_factory=set)

    @property
    def pk(self) -> str:
        return self.type["pk_column"]

    @property
    def title(self) -> str:
        title = self.type.get("title_column")
        return title if title and self.readable(title) else self.pk

    def readable(self, column: str) -> bool:
        return column.casefold() not in self.restricted

    def data_type(self, column: str) -> str | None:
        return next(
            (p["data_type"] for p in self.properties if p["column_name"] == column),
            None,
        )

    def shown_columns(self) -> list[str]:
        """The key, the title, then every visible property the caller may read."""
        out = [self.pk]
        for column in [self.title] + [
            p["column_name"] for p in self.properties if not p["hidden"]
        ]:
            if column not in out and self.readable(column):
                out.append(column)
        return out


def properties_of(
    table: dict[str, Any], overrides: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """A table's columns as properties: catalog order, overrides applied."""
    props = []
    for column in table.get("columns") or []:
        override = overrides.get(column["name"]) or {}
        props.append(
            {
                "column_name": column["name"],
                "label": override.get("display_name")
                or short_label(column.get("description"), column["name"]),
                "display_name": override.get("display_name"),
                "hidden": bool(override.get("hidden")),
                "description": column.get("description"),
                "data_type": column.get("data_type"),
            }
        )
    return props


def load_view(type_id: str, access: Any | None = None) -> TypeView | None:
    """*type_id* resolved for a caller with *access* (an ``AccessContext``)."""
    from auto_ontology.governance.enforce import hide_restricted_columns

    object_type = dal.get_object_type(type_id)
    if not object_type:
        return None
    tables = dal.fetch_catalog_tables([object_type["table_id"]])
    if not tables:
        return None
    table = tables[0]
    restricted: set[str] = set()
    if access is not None:
        allowed = hide_restricted_columns([table], access)[0]["columns"]
        kept = {c["name"] for c in allowed}
        restricted = {
            c["name"].casefold() for c in table["columns"] if c["name"] not in kept
        }
    return TypeView(
        type=object_type,
        table=table,
        properties=properties_of(table, dal.fetch_property_overrides(type_id)),
        restricted=restricted,
    )


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------


def literal(value: Any, data_type: str | None = None) -> exp.Expression:
    """*value* as a literal comparable with a column of *data_type*.

    Keys arrive as strings from a URL and as Python values from a row; the
    column's catalog type decides which literal the source database will
    compare without an implicit cast it may not have.
    """
    kind = (data_type or "").lower()
    if isinstance(value, bool):
        return exp.Boolean(this=value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if _TEXT_TYPE.search(kind):
        return exp.Literal.string(str(value))
    if isinstance(value, (int, float)):
        return exp.Literal.number(value)
    text = str(value)
    if _NUMERIC_TYPE.search(kind) and _NUMBER.fullmatch(text):
        return exp.Literal.number(text)
    return exp.Literal.string(text)


def _col(name: str) -> exp.Column:
    return exp.column(name, quoted=True)


def build_select(
    qualified_table: str,
    columns: list[str],
    dialect: str | None,
    *,
    where: exp.Expression | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> str:
    query = exp.select(*[_col(c) for c in columns]).from_(
        exp.to_table(qualified_table, dialect=dialect or None)
    )
    if where is not None:
        query = query.where(where)
    if order_by:
        query = query.order_by(_col(order_by))
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    return query.sql(dialect=dialect or None)


def search_condition(columns: list[str], needle: str) -> exp.Expression:
    """Any of *columns*, as text, contains *needle* (case-insensitive)."""
    pattern = exp.Literal.string(f"%{needle.lower()}%")
    conditions = [
        exp.Like(this=exp.Lower(this=exp.cast(_col(c), "VARCHAR")), expression=pattern)
        for c in columns
    ]
    return exp.or_(*conditions)


def equals(column: str, value: Any, data_type: str | None) -> exp.Expression:
    return exp.EQ(this=_col(column), expression=literal(value, data_type))


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def _load_connectors(subject_token: str | None) -> list[Any]:
    """The connectors to read through: the caller's own where a connection
    authenticates as the signed-in user, the shared ones everywhere else."""
    from auto_ontology.connectors import get_connectors

    if subject_token is None:
        return get_connectors()

    from auto_ontology.connectors.databricks_oauth import DatabricksOAuthError
    from auto_ontology.connectors.registry import get_connectors_for_subject_token

    try:
        return get_connectors_for_subject_token(subject_token)
    except DatabricksOAuthError as exc:
        raise ObjectQueryError(f"无法以当前登录用户的身份连接数据库：{exc}") from exc


@dataclass
class Reader:
    """Who is reading, resolved once per request and shared by its statements.

    An object page runs one statement per link; resolving the caller's
    policies, or exchanging their SSO token for a connector, once for each
    would repeat the same work for the same answer.
    """

    user_id: str | None
    #: The caller's ``AccessContext``.
    access: Any
    #: The caller's SSO token, when a connection authenticates as the user.
    subject_token: str | None = None
    _connectors: list[Any] | None = field(default=None, repr=False)

    def connector(self, database_name: str) -> Any:
        if self._connectors is None:
            self._connectors = _load_connectors(self.subject_token)
        for connector in self._connectors:
            if getattr(connector, "database_name", None) == database_name:
                return connector
        raise ObjectQueryError(f"找不到数据库连接：{database_name}")


def _run(
    view: TypeView,
    columns: list[str],
    reader: Reader,
    *,
    where: exp.Expression | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    from auto_ontology.subscriptions.service import RunError, run_query

    if not view.readable(view.pk):
        raise ObjectQueryError("没有读取该对象主键字段的权限")
    table = view.table
    connector = reader.connector(table["database_name"])
    sql = build_select(
        connector.qualify(table["schema_name"], table["name"]),
        columns,
        connector.dialect,
        where=where,
        order_by=view.pk,
        limit=limit,
        offset=offset,
    )
    try:
        return run_query(
            sql,
            table["database_name"],
            reader.user_id,
            f"对象浏览：{view.type['display_name']}",
            connector=connector,
            access=reader.access,
        ).rows
    except RunError as exc:
        raise ObjectQueryError(str(exc)) from exc


def _summary(view: TypeView, row: dict[str, Any]) -> dict[str, Any]:
    """An instance as a link to it: key, title, and the shown columns."""
    key = row.get(view.pk)
    title = row.get(view.title)
    return {
        "key": None if key is None else str(key),
        "title": str(title if title not in (None, "") else key),
        "values": row,
    }


def list_objects(
    view: TypeView,
    reader: Reader,
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """One page of instances, ordered by key, optionally searched by key/title."""
    limit = max(1, min(limit, MAX_PAGE))
    columns = view.shown_columns()
    where = None
    needle = (search or "").strip()
    if needle:
        where = search_condition(list(dict.fromkeys([view.pk, view.title])), needle)
    rows = _run(
        view, columns, reader, where=where, limit=limit + 1, offset=max(0, offset)
    )
    return {
        "columns": columns,
        "objects": [_summary(view, r) for r in rows[:limit]],
        "has_more": len(rows) > limit,
    }


def _linked(
    other: TypeView,
    column: str,
    value: Any,
    reader: Reader,
    limit: int,
) -> dict[str, Any]:
    if value is None:
        return {"objects": [], "has_more": False}
    if not other.readable(column):
        raise ObjectQueryError("没有读取关联字段的权限")
    rows = _run(
        other,
        other.shown_columns(),
        reader,
        where=equals(column, value, other.data_type(column)),
        limit=limit + 1,
    )
    return {
        "objects": [_summary(other, r) for r in rows[:limit]],
        "has_more": len(rows) > limit,
    }


def get_object(view: TypeView, key: str, reader: Reader) -> dict[str, Any] | None:
    """One instance with its properties and the instances linked to it.

    A link whose other end the caller cannot read is reported on that link
    alone; the rest of the page still loads.
    """
    type_id = view.type["id"]
    links = dal.list_link_types(type_id=type_id, status=s.OBJECT_ACTIVE)
    # The columns links join on are read even when hidden: hiding is about
    # what the page shows, not what it may use.
    columns = view.shown_columns()
    for link in links:
        for column in (
            link["source_column"] if link["object_type_id"] == type_id else None,
            link["target_column"] if link["target_object_type_id"] == type_id else None,
        ):
            if column and column not in columns and view.readable(column):
                columns.append(column)
    rows = _run(
        view,
        columns,
        reader,
        where=equals(view.pk, key, view.data_type(view.pk)),
        limit=1,
    )
    if not rows:
        return None
    row = rows[0]

    others: dict[str, TypeView | None] = {}

    def other_view(type_id: str) -> TypeView | None:
        if type_id not in others:
            loaded = load_view(type_id, reader.access)
            others[type_id] = (
                loaded if loaded and loaded.type["status"] == s.OBJECT_ACTIVE else None
            )
        return others[type_id]

    out_links = []
    for link in links:
        # A self-link (a category's parent) is read both ways on one page.
        directions = []
        if link["object_type_id"] == type_id:
            directions.append("out")
        if link["target_object_type_id"] == type_id:
            directions.append("in")
        for direction in directions:
            outgoing = direction == "out"
            other_id = (
                link["target_object_type_id"] if outgoing else link["object_type_id"]
            )
            other = other_view(other_id)
            if other is None:
                continue
            entry: dict[str, Any] = {
                "link_id": link["id"],
                "direction": direction,
                "name": link["display_name"]
                if outgoing
                else link["reverse_display_name"],
                "object_type": {
                    "id": other.type["id"],
                    "display_name": other.type["display_name"],
                },
                "many": not outgoing,
            }
            own_column = link["source_column"] if outgoing else link["target_column"]
            their_column = link["target_column"] if outgoing else link["source_column"]
            try:
                if own_column not in row:
                    raise ObjectQueryError("没有读取关联字段的权限")
                entry.update(
                    _linked(
                        other,
                        their_column,
                        row[own_column],
                        reader,
                        1 if outgoing else LINKED_LIMIT,
                    )
                )
            except ObjectQueryError as exc:
                entry.update({"objects": [], "has_more": False, "error": str(exc)})
            out_links.append(entry)

    shown = view.shown_columns()
    return {
        **_summary(view, {k: v for k, v in row.items() if k in shown}),
        "links": out_links,
    }
