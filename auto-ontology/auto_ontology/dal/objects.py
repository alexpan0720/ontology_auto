# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Object types, their property overrides, and the link types between them.

A type's properties are not stored: they are its table's columns, read from the
catalog on every call and overlaid with ``object_property`` where someone
renamed or hid one. That keeps a re-ingest that adds a column from needing a
write here, and a dropped column from leaving a property behind.

Orchestration (candidate generation, instance queries) stays in
``auto_ontology/objects/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store, write_transaction


class ObjectTypeConflict(Exception):
    """The table already backs an object type."""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Catalog reads the object layer is built from
# ---------------------------------------------------------------------------


def _table_location() -> Any:
    t, sc, db = s.catalog_table, s.catalog_schema, s.catalog_database
    return (
        select(
            t.c.id,
            t.c.name,
            t.c.description,
            t.c.pk,
            t.c.table_type,
            t.c.is_junction_table,
            sc.c.name.label("schema_name"),
            db.c.name.label("database_name"),
            db.c.dialect,
        )
        .join(sc, sc.c.id == t.c.schema_id)
        .join(db, db.c.id == sc.c.database_id)
    )


def fetch_catalog_tables(table_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Tables with their location and columns, in the catalog's column order."""
    query = _table_location()
    if table_ids is not None:
        if not table_ids:
            return []
        query = query.where(s.catalog_table.c.id.in_(table_ids))
    tables = store().query_read(query.order_by(s.catalog_table.c.name))
    if not tables:
        return []
    c = s.catalog_column
    columns = store().query_read(
        select(c.c.table_id, c.c.name, c.c.description, c.c.data_type)
        .where(c.c.table_id.in_([t["id"] for t in tables]))
        .order_by(c.c.table_id, c.c.ordinal_position.nulls_last(), c.c.name)
    )
    by_table: dict[str, list[dict[str, Any]]] = {}
    for col in columns:
        by_table.setdefault(col.pop("table_id"), []).append(col)
    return [
        {**t, "pk": list(t["pk"] or []), "columns": by_table.get(t["id"], [])}
        for t in tables
    ]


def fetch_key_pairs() -> list[dict[str, Any]]:
    """Every column pair a link can be built on: declared and semantic FKs.

    A semantic FK points a column at an attribute; the column it references is
    the one on the attribute's own table carrying that attribute.
    """
    src, tgt = s.catalog_column.alias("src"), s.catalog_column.alias("tgt")
    fk = s.column__foreign_key
    declared = store().query_read(
        select(
            src.c.table_id.label("source_table_id"),
            src.c.name.label("source_column"),
            tgt.c.table_id.label("target_table_id"),
            tgt.c.name.label("target_column"),
        )
        .select_from(fk)
        .join(src, src.c.id == fk.c.source_column_id)
        .join(tgt, tgt.c.id == fk.c.target_column_id)
    )
    sfk, attr, has = s.column__semantic_fk, s.column_attribute, s.column__has_attribute
    semantic = store().query_read(
        select(
            src.c.table_id.label("source_table_id"),
            src.c.name.label("source_column"),
            tgt.c.table_id.label("target_table_id"),
            tgt.c.name.label("target_column"),
        )
        .select_from(sfk)
        .join(src, src.c.id == sfk.c.column_id)
        .join(attr, attr.c.id == sfk.c.attribute_id)
        .join(has, has.c.attribute_id == attr.c.id)
        .join(tgt, and_(tgt.c.id == has.c.column_id, tgt.c.table_id == attr.c.table_id))
        .where(tgt.c.id != src.c.id)
        .distinct()
    )
    return [{**r, "origin": s.LINK_FOREIGN_KEY} for r in declared] + [
        {**r, "origin": s.LINK_SEMANTIC_FK} for r in semantic
    ]


# ---------------------------------------------------------------------------
# Object types
# ---------------------------------------------------------------------------


def _type_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "table_id": row["table_id"],
        "display_name": row["display_name"],
        "description": row["description"],
        "pk_column": row["pk_column"],
        "title_column": row["title_column"],
        "status": row["status"],
        "table_name": row["table_name"],
        "schema_name": row["schema_name"],
        "database_name": row["database_name"],
        "created": _iso(row["created"]),
        "modified": _iso(row["modified"]),
    }


def _type_select() -> Any:
    o, t, sc, db = s.object_type, s.catalog_table, s.catalog_schema, s.catalog_database
    return (
        select(
            o,
            t.c.name.label("table_name"),
            sc.c.name.label("schema_name"),
            db.c.name.label("database_name"),
        )
        .join(t, t.c.id == o.c.table_id)
        .join(sc, sc.c.id == t.c.schema_id)
        .join(db, db.c.id == sc.c.database_id)
    )


def list_object_types(status: str | None = None) -> list[dict[str, Any]]:
    """Types with how many links each takes part in, ordered by name."""
    query = _type_select()
    if status:
        query = query.where(s.object_type.c.status == status)
    rows = store().query_read(query.order_by(s.object_type.c.display_name))
    lt = s.link_type
    counts = store().query_read(
        select(lt.c.object_type_id, lt.c.target_object_type_id).where(
            lt.c.status == s.OBJECT_ACTIVE
        )
    )
    link_count: dict[str, int] = {}
    for link in counts:
        for type_id in {link["object_type_id"], link["target_object_type_id"]}:
            link_count[type_id] = link_count.get(type_id, 0) + 1
    return [{**_type_public(r), "link_count": link_count.get(r["id"], 0)} for r in rows]


def get_object_type(type_id: str) -> dict[str, Any] | None:
    rows = store().query_read(_type_select().where(s.object_type.c.id == type_id))
    return _type_public(rows[0]) if rows else None


def get_object_types(type_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not type_ids:
        return {}
    rows = store().query_read(_type_select().where(s.object_type.c.id.in_(type_ids)))
    return {r["id"]: _type_public(r) for r in rows}


def object_type_table_ids() -> set[str]:
    rows = store().query_read(select(s.object_type.c.table_id))
    return {r["table_id"] for r in rows}


def fetch_property_overrides(type_id: str) -> dict[str, dict[str, Any]]:
    p = s.object_property
    rows = store().query_read(
        select(p.c.column_name, p.c.display_name, p.c.hidden).where(
            p.c.object_type_id == type_id
        )
    )
    return {r["column_name"]: r for r in rows}


def create_object_types(
    specs: list[dict[str, Any]], *, created_by: str | None
) -> list[str]:
    """Insert types (one per table); a table that already has one is skipped."""
    if not specs:
        return []
    rows = store().query_write(
        pg_insert(s.object_type)
        .values(
            [
                {
                    "table_id": spec["table_id"],
                    "display_name": spec["display_name"],
                    "description": spec.get("description"),
                    "pk_column": spec["pk_column"],
                    "title_column": spec.get("title_column"),
                    "status": spec.get("status", s.OBJECT_CANDIDATE),
                    "created_by": created_by,
                }
                for spec in specs
            ]
        )
        .on_conflict_do_nothing(index_elements=[s.object_type.c.table_id])
        .returning(s.object_type.c.id)
    )
    return [r["id"] for r in rows]


def create_object_type(spec: dict[str, Any], *, created_by: str | None) -> str:
    ids = create_object_types([spec], created_by=created_by)
    if not ids:
        raise ObjectTypeConflict(spec["table_id"])
    return ids[0]


TYPE_EDITABLE = ("display_name", "description", "pk_column", "title_column", "status")


def update_object_type(
    type_id: str,
    values: dict[str, Any],
    *,
    properties: list[dict[str, Any]] | None,
    modified_by: str | None,
) -> bool:
    """Edit a type and, when *properties* is given, replace its overrides.

    An override that says nothing (no name, not hidden) is not stored.
    """
    with write_transaction():
        rows = store().query_write(
            update(s.object_type)
            .where(s.object_type.c.id == type_id)
            .values(
                **{k: v for k, v in values.items() if k in TYPE_EDITABLE},
                modified=_now(),
                modified_by=modified_by,
            )
            .returning(s.object_type.c.id)
        )
        if not rows:
            return False
        if properties is not None:
            p = s.object_property
            store().query_write(delete(p).where(p.c.object_type_id == type_id))
            kept = [
                {
                    "object_type_id": type_id,
                    "column_name": prop["column_name"],
                    "display_name": (prop.get("display_name") or "").strip() or None,
                    "hidden": bool(prop.get("hidden")),
                }
                for prop in properties
                if (prop.get("display_name") or "").strip() or prop.get("hidden")
            ]
            if kept:
                store().query_write(insert(p).values(kept))
    return True


def set_status(type_ids: list[str], status: str, *, modified_by: str | None) -> int:
    """Set many types' status; activating a type does not activate its links."""
    if not type_ids:
        return 0
    rows = store().query_write(
        update(s.object_type)
        .where(s.object_type.c.id.in_(type_ids))
        .values(status=status, modified=_now(), modified_by=modified_by)
        .returning(s.object_type.c.id)
    )
    return len(rows)


def delete_object_types(type_ids: list[str]) -> int:
    """Delete types; their overrides and every link touching them cascade."""
    if not type_ids:
        return 0
    rows = store().query_write(
        delete(s.object_type)
        .where(s.object_type.c.id.in_(type_ids))
        .returning(s.object_type.c.id)
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Link types
# ---------------------------------------------------------------------------


def _link_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "object_type_id": row["object_type_id"],
        "target_object_type_id": row["target_object_type_id"],
        "source_column": row["source_column"],
        "target_column": row["target_column"],
        "display_name": row["display_name"],
        "reverse_display_name": row["reverse_display_name"],
        "origin": row["origin"],
        "status": row["status"],
    }


def list_link_types(
    *, type_id: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """Links, optionally only those touching *type_id* from either end."""
    lt = s.link_type
    query = select(lt)
    if type_id:
        query = query.where(
            or_(lt.c.object_type_id == type_id, lt.c.target_object_type_id == type_id)
        )
    if status:
        query = query.where(lt.c.status == status)
    rows = store().query_read(query.order_by(lt.c.created, lt.c.id))
    return [_link_public(r) for r in rows]


def get_link_type(link_id: str) -> dict[str, Any] | None:
    rows = store().query_read(select(s.link_type).where(s.link_type.c.id == link_id))
    return _link_public(rows[0]) if rows else None


def link_keys() -> set[tuple[str, str, str]]:
    """``(source type, source column, target type)`` of every existing link."""
    lt = s.link_type
    rows = store().query_read(
        select(lt.c.object_type_id, lt.c.source_column, lt.c.target_object_type_id)
    )
    return {
        (r["object_type_id"], r["source_column"], r["target_object_type_id"])
        for r in rows
    }


def create_link_types(
    specs: list[dict[str, Any]], *, created_by: str | None
) -> list[str]:
    """Insert links; one that already exists for the same key is skipped."""
    if not specs:
        return []
    rows = store().query_write(
        pg_insert(s.link_type)
        .values(
            [
                {
                    "object_type_id": spec["object_type_id"],
                    "target_object_type_id": spec["target_object_type_id"],
                    "source_column": spec["source_column"],
                    "target_column": spec["target_column"],
                    "display_name": spec["display_name"],
                    "reverse_display_name": spec["reverse_display_name"],
                    "origin": spec.get("origin", s.LINK_MANUAL),
                    "status": spec.get("status", s.OBJECT_CANDIDATE),
                    "created_by": created_by,
                }
                for spec in specs
            ]
        )
        .on_conflict_do_nothing(constraint="uq_link_type_source")
        .returning(s.link_type.c.id)
    )
    return [r["id"] for r in rows]


LINK_EDITABLE = ("display_name", "reverse_display_name", "status")


def update_link_type(
    link_id: str, values: dict[str, Any], *, modified_by: str | None
) -> bool:
    rows = store().query_write(
        update(s.link_type)
        .where(s.link_type.c.id == link_id)
        .values(
            **{k: v for k, v in values.items() if k in LINK_EDITABLE},
            modified=_now(),
            modified_by=modified_by,
        )
        .returning(s.link_type.c.id)
    )
    return bool(rows)


def set_link_status(
    link_ids: list[str], status: str, *, modified_by: str | None
) -> int:
    if not link_ids:
        return 0
    rows = store().query_write(
        update(s.link_type)
        .where(s.link_type.c.id.in_(link_ids))
        .values(status=status, modified=_now(), modified_by=modified_by)
        .returning(s.link_type.c.id)
    )
    return len(rows)


def delete_link_type(link_id: str) -> bool:
    rows = store().query_write(
        delete(s.link_type)
        .where(s.link_type.c.id == link_id)
        .returning(s.link_type.c.id)
    )
    return bool(rows)


def counts() -> dict[str, int]:
    """How many types and links are active and awaiting review."""
    o, lt = s.object_type, s.link_type
    type_rows = store().query_read(
        select(o.c.status, func.count().label("n")).group_by(o.c.status)
    )
    link_rows = store().query_read(
        select(lt.c.status, func.count().label("n")).group_by(lt.c.status)
    )
    by_type = {r["status"]: r["n"] for r in type_rows}
    by_link = {r["status"]: r["n"] for r in link_rows}
    return {
        "active_types": by_type.get(s.OBJECT_ACTIVE, 0),
        "candidate_types": by_type.get(s.OBJECT_CANDIDATE, 0),
        "active_links": by_link.get(s.OBJECT_ACTIVE, 0),
        "candidate_links": by_link.get(s.OBJECT_CANDIDATE, 0),
    }


def fetch_object_context(table_ids: list[str]) -> dict[str, dict[str, Any]]:
    """The active object each of *table_ids* backs, with its active links.

    Keyed by table id; a table backing no active type is absent. Each link is
    told from this table's side — the column on it, the other table and its
    column — and only when both ends are active, so a question never sees a
    relationship nobody has confirmed.
    """
    if not table_ids:
        return {}
    types = {t["id"]: t for t in list_object_types(status=s.OBJECT_ACTIVE)}
    wanted = set(table_ids)
    out: dict[str, dict[str, Any]] = {
        t["table_id"]: {
            "name": t["display_name"],
            "description": t["description"],
            "links": [],
        }
        for t in types.values()
        if t["table_id"] in wanted
    }
    if not out:
        return out
    for link in list_link_types(status=s.OBJECT_ACTIVE):
        source = types.get(link["object_type_id"])
        target = types.get(link["target_object_type_id"])
        if source is None or target is None:
            continue
        ends = (
            (source, link["source_column"], target, link["target_column"], "out"),
            (target, link["target_column"], source, link["source_column"], "in"),
        )
        for own, own_column, other, other_column, direction in ends:
            entry = out.get(own["table_id"])
            if entry is None:
                continue
            entry["links"].append(
                {
                    "direction": direction,
                    "name": link["display_name"]
                    if direction == "out"
                    else link["reverse_display_name"],
                    "column": own_column,
                    "other_object": other["display_name"],
                    "other_table_id": other["table_id"],
                    "other_table": other["table_name"],
                    "other_schema": other["schema_name"],
                    "other_column": other_column,
                }
            )
    return out
