# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Object layer orchestration: generating candidates and describing a type."""

from __future__ import annotations

from typing import Any

from auto_ontology.dal import objects as dal
from auto_ontology.dal import schema as s
from auto_ontology.objects import generate as gen
from auto_ontology.objects.instances import load_view


def generate(created_by: str | None) -> dict[str, Any]:
    """Propose a type for every keyed table without one, then links between types.

    Safe to repeat: a table that has a type, or a link already defined between
    the same columns, is left as it is — including one someone deleted as a
    candidate and so will see proposed again.
    """
    tables = dal.fetch_catalog_tables()
    specs, keyless = gen.type_candidates(tables, dal.object_type_table_ids())
    created_types = dal.create_object_types(specs, created_by=created_by)

    types_by_table = {t["table_id"]: t for t in dal.list_object_types()}
    link_specs = gen.link_candidates(
        types_by_table,
        dal.fetch_key_pairs(),
        dal.link_keys(),
        {t["id"]: t["columns"] for t in tables},
    )
    created_links = dal.create_link_types(link_specs, created_by=created_by)
    return {
        "types": len(created_types),
        "links": len(created_links),
        "keyless_tables": keyless,
    }


def accept(type_ids: list[str], modified_by: str | None) -> dict[str, int]:
    """Activate types, then every candidate link whose two ends are now active."""
    types = dal.set_status(type_ids, s.OBJECT_ACTIVE, modified_by=modified_by)
    active = {t["id"] for t in dal.list_object_types(status=s.OBJECT_ACTIVE)}
    ready = [
        link["id"]
        for link in dal.list_link_types(status=s.OBJECT_CANDIDATE)
        if link["object_type_id"] in active
        and link["target_object_type_id"] in active
        and (
            link["object_type_id"] in type_ids
            or link["target_object_type_id"] in type_ids
        )
    ]
    links = dal.set_link_status(ready, s.OBJECT_ACTIVE, modified_by=modified_by)
    return {"types": types, "links": links}


def describe(type_id: str) -> dict[str, Any] | None:
    """A type with its properties and the links on both its ends."""
    view = load_view(type_id)
    if view is None:
        return None
    links = dal.list_link_types(type_id=type_id)
    others = dal.get_object_types(
        list(
            {link["object_type_id"] for link in links}
            | {link["target_object_type_id"] for link in links}
        )
    )
    return {
        **view.type,
        "table_description": view.table.get("description"),
        "properties": view.properties,
        "links": [
            {
                **link,
                "source_type": _brief(others.get(link["object_type_id"])),
                "target_type": _brief(others.get(link["target_object_type_id"])),
            }
            for link in links
        ],
    }


def _brief(object_type: dict[str, Any] | None) -> dict[str, Any] | None:
    if object_type is None:
        return None
    return {
        "id": object_type["id"],
        "display_name": object_type["display_name"],
        "status": object_type["status"],
        "table_name": object_type["table_name"],
    }


def table_columns(table_id: str) -> list[dict[str, Any]] | None:
    tables = dal.fetch_catalog_tables([table_id])
    return tables[0]["columns"] if tables else None


def new_type_spec(table_id: str, pk_column: str | None) -> dict[str, Any] | None:
    """A type for *table_id* as generation would propose it, keyed on *pk_column*."""
    tables = dal.fetch_catalog_tables([table_id])
    if not tables:
        return None
    table = tables[0]
    pk = pk_column or gen.key_column(table)
    if pk is None:
        return None
    return {
        "table_id": table_id,
        "display_name": gen.type_label(table, pk),
        "description": table.get("description"),
        "pk_column": pk,
        "title_column": gen.title_column(table["columns"], pk),
    }
