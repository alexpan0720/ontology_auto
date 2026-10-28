# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reads behind an answer's provenance: what it was built on, and how trusted.

An answer is traced from the catalog ids its executed SQL resolved to, not from
what retrieval merely surfaced, so every item listed is one the SQL actually
reads (tables, and the attributes of the columns it touches) or is defined over
only those tables (sql attributes, terms).

Statuses use the same three values as the rest of the UI. Tables and attributes
carry a single flag, so they are only ever ``certified`` or ``pending``; a Term
uses the shared rollup in :func:`auto_ontology.dal.terms._certification`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import literal, select

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store
from auto_ontology.dal.terms import _certification


def _status(flag: Any) -> str:
    return "certified" if flag else "pending"


def fetch_answer_provenance(
    table_ids: list[str],
    column_ids: list[str],
    sql_attribute_ids: list[str],
    extra_term_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Tables, terms, sql attributes and column attributes behind one answer.

    *table_ids* / *column_ids* are the catalog ids the executed SQL resolved to.
    *sql_attribute_ids* are the candidates the generator was shown; only those
    whose SQL reads nothing outside *table_ids* are kept. *extra_term_ids* adds
    terms the question was matched to directly.
    """
    table_ids = sorted(set(table_ids))
    if not table_ids:
        return {
            "tables": [],
            "terms": [],
            "sql_attributes": [],
            "column_attributes": [],
        }
    db = store()

    tables = db.query_read(
        select(
            s.catalog_table.c.id,
            s.catalog_table.c.name,
            s.catalog_table.c.description_certified,
            s.catalog_schema.c.id.label("schema_id"),
            s.catalog_schema.c.name.label("schema_name"),
            s.catalog_database.c.id.label("database_id"),
            s.catalog_database.c.name.label("database_name"),
        )
        .select_from(
            s.catalog_table.join(
                s.catalog_schema, s.catalog_schema.c.id == s.catalog_table.c.schema_id
            ).join(
                s.catalog_database,
                s.catalog_database.c.id == s.catalog_schema.c.database_id,
            )
        )
        .where(s.catalog_table.c.id.in_(table_ids))
        .order_by(s.catalog_table.c.name)
    )

    column_attributes = []
    if column_ids:
        column_attributes = db.query_read(
            select(
                s.column_attribute.c.id,
                s.column_attribute.c.name,
                s.column_attribute.c.certified,
                s.column_attribute__term.c.term_id,
            )
            .distinct()
            .select_from(
                s.column__has_attribute.join(
                    s.column_attribute,
                    s.column_attribute.c.id == s.column__has_attribute.c.attribute_id,
                ).outerjoin(
                    s.column_attribute__term,
                    s.column_attribute__term.c.attribute_id == s.column_attribute.c.id,
                )
            )
            .where(s.column__has_attribute.c.column_id.in_(sorted(set(column_ids))))
            .order_by(s.column_attribute.c.name)
        )

    sql_attributes = []
    if sql_attribute_ids:
        # Defined only over tables this SQL reads: a metric over some other
        # table was retrieved but could not have shaped this query.
        reads_elsewhere = (
            select(literal(1))
            .select_from(
                s.sql_attribute__sql.join(
                    s.sql_query__table,
                    s.sql_query__table.c.sql_query_id
                    == s.sql_attribute__sql.c.sql_query_id,
                )
            )
            .where(
                s.sql_attribute__sql.c.attribute_id == s.sql_attribute.c.id,
                s.sql_query__table.c.table_id.notin_(table_ids),
            )
            .correlate(s.sql_attribute)
            .exists()
        )
        sql_attributes = db.query_read(
            select(
                s.sql_attribute.c.id,
                s.sql_attribute.c.name,
                s.sql_attribute.c.certified,
                s.sql_attribute__term.c.term_id,
            )
            .select_from(
                s.sql_attribute.outerjoin(
                    s.sql_attribute__term,
                    s.sql_attribute__term.c.attribute_id == s.sql_attribute.c.id,
                )
            )
            .where(
                s.sql_attribute.c.id.in_(sorted(set(sql_attribute_ids))),
                ~reads_elsewhere,
            )
            .order_by(s.sql_attribute.c.name)
        )

    represented = db.query_read(
        select(s.table__term.c.term_id).where(s.table__term.c.table_id.in_(table_ids))
    )
    term_ids = {row["term_id"] for row in represented}
    term_ids.update(row["term_id"] for row in column_attributes if row["term_id"])
    term_ids.update(row["term_id"] for row in sql_attributes if row["term_id"])
    term_ids.update(t for t in extra_term_ids if t)

    terms = []
    if term_ids:
        terms = db.query_read(
            select(
                s.term.c.id,
                s.term.c.name,
                _certification(None).label("certification"),
            )
            .where(s.term.c.id.in_(sorted(term_ids)))
            .order_by(s.term.c.name)
        )

    return {
        "tables": [
            {
                "id": row["id"],
                "name": row["name"],
                "schema_id": row["schema_id"],
                "schema_name": row["schema_name"],
                "database_id": row["database_id"],
                "database_name": row["database_name"],
                "status": _status(row["description_certified"]),
            }
            for row in tables
        ],
        "terms": [
            {"id": row["id"], "name": row["name"], "status": row["certification"]}
            for row in terms
        ],
        "sql_attributes": [
            {
                "id": row["id"],
                "name": row["name"],
                "term_id": row["term_id"],
                "status": _status(row["certified"]),
            }
            for row in sql_attributes
        ],
        "column_attributes": [
            {
                "id": row["id"],
                "name": row["name"],
                "term_id": row["term_id"],
                "status": _status(row["certified"]),
            }
            for row in column_attributes
        ],
    }
