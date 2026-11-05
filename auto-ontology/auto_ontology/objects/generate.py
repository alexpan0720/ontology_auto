# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Propose object and link types from the catalog.

Deterministic on purpose: the catalog already says what an object is (a table
with a single-column key) and how two relate (a declared or semantic foreign
key), and the names come from the descriptions ingestion and compilation
wrote. Everything proposed starts as a candidate for a person to confirm.

The functions here are pure — catalog rows in, specs out — so the rules can be
tested without a database. :func:`auto_ontology.objects.service.generate` does
the reads and writes around them.
"""

from __future__ import annotations

import re
from typing import Any

#: Warehouse layer prefixes that say nothing about the business object.
_LAYER_PREFIX = re.compile(r"^(dim|fact|fct|dwd|dws|dwm|ods|ads|tb|tbl|t)_", re.I)
#: Where a description's first clause ends.
_CLAUSE_END = re.compile(r"[，。,.;；:：\n（(]")
_TITLE_NAME = re.compile(
    r"(^|_)(name|title|full_name|nickname|display_name|username|label|subject)$",
    re.I,
)
_TITLE_WORDS = ("名称", "姓名", "标题", "名字")
#: What a key column's description says after naming the thing it identifies.
_KEY_SUFFIX = re.compile(r"\s*(id|编号|编码|代码|主键)$", re.I)
#: A label longer than this reads as a sentence, not a name.
MAX_LABEL = 24


def short_label(description: str | None, fallback: str) -> str:
    """The first clause of *description* when it is short enough to be a name.

    ``"客户信息表，记录注册客户"`` -> ``"客户信息"``. A description that is a
    sentence rather than a name falls back to *fallback*.
    """
    head = _CLAUSE_END.split((description or "").strip(), maxsplit=1)[0].strip()
    if head.endswith("表") and len(head) > 1:
        head = head[:-1]
    if head and len(head) <= MAX_LABEL:
        return head
    return fallback


def type_label(table: dict[str, Any], pk: str | None = None) -> str:
    """The table's own description, else what its key's description identifies.

    Tables often carry no description while their key does: ``"客户ID，主键"``
    names the object ``客户`` better than a table name like ``customers``.
    """
    label = short_label(table.get("description"), "")
    if label:
        return label
    key = next((c for c in table.get("columns") or [] if c["name"] == pk), None)
    if key:
        label = _KEY_SUFFIX.sub("", short_label(key.get("description"), "")).strip()
        if label:
            return label
    name = table["name"]
    return _LAYER_PREFIX.sub("", name) or name


def key_column(table: dict[str, Any]) -> str | None:
    """The column an instance is identified by, or None when there is none.

    A declared single-column key wins. Without one, a column named ``id`` or
    ``<table>_id`` (singular or plural table name) is taken, since many
    warehouses declare no keys at all. A composite key is not an identity a
    page can be addressed by, so such a table gets no type.
    """
    pk = table.get("pk") or []
    if len(pk) == 1:
        return pk[0]
    if pk:
        return None
    names = {c["name"].lower(): c["name"] for c in table.get("columns") or []}
    base = _LAYER_PREFIX.sub("", table["name"]).lower()
    for guess in ("id", f"{base}_id", f"{base.rstrip('s')}_id"):
        if guess in names:
            return names[guess]
    return None


def title_column(columns: list[dict[str, Any]], pk: str) -> str | None:
    """The column an instance is called by: a name or title, if there is one."""
    others = [c for c in columns if c["name"] != pk]
    for col in others:
        if _TITLE_NAME.search(col["name"]):
            return col["name"]
    for col in others:
        if any(word in (col.get("description") or "") for word in _TITLE_WORDS):
            return col["name"]
    return None


def is_view(table: dict[str, Any]) -> bool:
    return "VIEW" in (table.get("table_type") or "").upper()


def type_candidates(
    tables: list[dict[str, Any]], taken_table_ids: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Specs for tables with no type yet, and the names of tables left out.

    Views are left out silently — a view is a query, not a thing — and so is a
    table without a single-column key, but that one is reported, since
    declaring the key is how to fix it. A table compilation flagged as a
    junction is kept when it has its own key: an order line joins an order to
    a product, and is still a thing with a quantity. A pure junction has a
    composite key and is left out by that rule.
    """
    specs: list[dict[str, Any]] = []
    keyless: list[str] = []
    for table in tables:
        if table["id"] in taken_table_ids or is_view(table):
            continue
        pk = key_column(table)
        if pk is None:
            keyless.append(table["name"])
            continue
        specs.append(
            {
                "table_id": table["id"],
                "display_name": type_label(table, pk),
                "description": table.get("description"),
                "pk_column": pk,
                "title_column": title_column(table.get("columns") or [], pk),
            }
        )
    return specs, keyless


def link_candidates(
    types_by_table: dict[str, dict[str, Any]],
    key_pairs: list[dict[str, Any]],
    existing: set[tuple[str, str, str]],
    columns_by_table: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Specs for links not yet defined, between tables that both have a type.

    Names are the two types' names — "订单" points at "客户", read back as the
    customer's "订单". When one type points at another through more than one
    column (a buyer and a seller who are both users), each is told apart by its
    column.
    """
    seen = set(existing)
    picked: list[dict[str, Any]] = []
    for pair in key_pairs:
        source = types_by_table.get(pair["source_table_id"])
        target = types_by_table.get(pair["target_table_id"])
        if not source or not target:
            continue
        if (
            source["id"] == target["id"]
            and pair["source_column"] == pair["target_column"]
        ):
            continue
        key = (source["id"], pair["source_column"], target["id"])
        if key in seen:
            continue
        seen.add(key)
        picked.append({**pair, "source": source, "target": target})

    per_pair: dict[tuple[str, str], int] = {}
    for src_id, _, tgt_id in seen:
        per_pair[(src_id, tgt_id)] = per_pair.get((src_id, tgt_id), 0) + 1

    specs = []
    for link in picked:
        source, target = link["source"], link["target"]
        forward, reverse = target["display_name"], source["display_name"]
        if per_pair[(source["id"], target["id"])] > 1:
            column = next(
                (
                    c
                    for c in columns_by_table.get(link["source_table_id"], [])
                    if c["name"] == link["source_column"]
                ),
                {"name": link["source_column"]},
            )
            label = short_label(column.get("description"), column["name"])
            forward, reverse = f"{forward}（{label}）", f"{reverse}（{label}）"
        specs.append(
            {
                "object_type_id": source["id"],
                "target_object_type_id": target["id"],
                "source_column": link["source_column"],
                "target_column": link["target_column"],
                "display_name": forward,
                "reverse_display_name": reverse,
                "origin": link["origin"],
            }
        )
    return specs
