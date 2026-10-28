# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for data governance: access policies, access audit, verified queries.

Who may call what is decided at the Next.js gateway (``withPermission``); these
handlers trust it, as every router here does, and take the caller's identity
from the forwarded header only to record authorship.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from auto_ontology.dal import governance as dal
from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store
from auto_ontology.server.identity import resolve_internal_user

router = APIRouter()


def _fail(exc: dal.PolicyError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Access policies
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    kind: Literal["column", "row", "mask"]
    table_id: str
    column_name: str | None = None
    predicate: str | None = None
    mask_style: str | None = None
    group_ids: list[str] = []
    description: str | None = None
    enabled: bool = True


class PolicyUpdate(BaseModel):
    column_name: str | None = None
    predicate: str | None = None
    mask_style: str | None = None
    group_ids: list[str] | None = None
    description: str | None = None
    enabled: bool | None = None


@router.get("/access-policies")
def list_access_policies() -> dict[str, Any]:
    """List every column and row access policy."""
    rows = dal.list_policies()
    return {"data": rows, "count": len(rows)}


@router.get("/access-policies/options")
def access_policy_options() -> dict[str, Any]:
    """Tables (with their columns) and user groups a policy can target."""
    tables = store().query_read(
        select(
            s.catalog_table.c.id,
            s.catalog_table.c.name,
            s.catalog_schema.c.name.label("schema_name"),
            s.catalog_database.c.name.label("database_name"),
            func.array_agg(s.catalog_column.c.name).label("columns"),
        )
        .select_from(
            s.catalog_table.join(
                s.catalog_schema, s.catalog_schema.c.id == s.catalog_table.c.schema_id
            )
            .join(
                s.catalog_database,
                s.catalog_database.c.id == s.catalog_schema.c.database_id,
            )
            .outerjoin(
                s.catalog_column, s.catalog_column.c.table_id == s.catalog_table.c.id
            )
        )
        .group_by(
            s.catalog_table.c.id,
            s.catalog_table.c.name,
            s.catalog_schema.c.name,
            s.catalog_database.c.name,
        )
        .order_by(
            s.catalog_database.c.name, s.catalog_schema.c.name, s.catalog_table.c.name
        )
    )
    groups = store().query_read(
        select(s.user_group.c.id, s.user_group.c.name, s.user_group.c.role).order_by(
            s.user_group.c.name
        )
    )
    return {
        "tables": [
            {**t, "columns": sorted(c for c in (t["columns"] or []) if c)}
            for t in tables
        ],
        "groups": groups,
    }


@router.post("/access-policies", status_code=201)
def create_access_policy(body: PolicyCreate, request: Request) -> dict[str, str]:
    """Create a column or row access policy."""
    try:
        policy_id = dal.create_policy(
            **body.model_dump(),
            created_by=resolve_internal_user(request, required=False),
        )
    except dal.PolicyError as exc:
        raise _fail(exc) from exc
    return {"id": policy_id}


@router.patch("/access-policies/{policy_id}")
def update_access_policy(policy_id: str, body: PolicyUpdate) -> dict[str, bool]:
    """Edit a policy's target, groups, description or enabled flag."""
    try:
        found = dal.update_policy(policy_id, body.model_dump(exclude_unset=True))
    except dal.PolicyError as exc:
        raise _fail(exc) from exc
    if not found:
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"ok": True}


@router.delete("/access-policies/{policy_id}")
def delete_access_policy(policy_id: str) -> dict[str, bool]:
    """Delete a policy."""
    if not dal.delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"ok": True}


@router.post("/access-policies/restrict-pii")
def restrict_pii(request: Request) -> dict[str, int]:
    """Add a mask policy for every PII-tagged column that has no policy yet.

    Identifier columns (``id``, ``*_id``) are skipped and counted in
    ``skipped_keys``: masking a join key would make joins pair wrong rows.
    """
    created, skipped_keys = dal.restrict_pii_columns(
        created_by=resolve_internal_user(request, required=False)
    )
    return {"created": created, "skipped_keys": skipped_keys}


# ---------------------------------------------------------------------------
# Access audit
# ---------------------------------------------------------------------------


@router.get("/access-audit")
def list_access_audit(
    user_id: str | None = Query(None),
    decision: Literal["allowed", "filtered", "blocked"] | None = Query(None),
    q: str | None = Query(None, description="Search the question and SQL"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Page through the access audit trail, newest first."""
    result = dal.list_audit(
        user_id=user_id, decision=decision, search=q, skip=skip, limit=limit
    )
    users = _user_names({row["user_id"] for row in result["data"] if row["user_id"]})
    for row in result["data"]:
        row["user_name"] = users.get(row["user_id"], row["user_id"])
    return result


def _user_names(user_ids: set[str]) -> dict[str, str]:
    """Display names for *user_ids* from the Better Auth ``user`` table."""
    if not user_ids:
        return {}
    import psycopg
    from psycopg.rows import dict_row

    from auto_ontology.infra.postgres import (
        FRONTEND_SCHEMA,
        get_postgres_connection_string,
    )

    with psycopg.connect(get_postgres_connection_string(), connect_timeout=3) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f'SELECT id, name, email FROM {FRONTEND_SCHEMA}."user" WHERE id = ANY(%s)',
                (list(user_ids),),
            )
            return {r["id"]: r["name"] or r["email"] for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# Verified queries
# ---------------------------------------------------------------------------


class VerifiedCreate(BaseModel):
    question: str
    sql: str
    database_name: str | None = None
    note: str | None = None
    status: Literal["pending", "certified"] = "pending"


class VerifiedSubmit(BaseModel):
    question: str
    sql: str
    database_name: str | None = None
    note: str | None = None


class VerifiedUpdate(BaseModel):
    question: str | None = None
    sql: str | None = None
    database_name: str | None = None
    note: str | None = None
    status: Literal["pending", "certified", "rejected"] | None = None


@router.get("/verified-queries")
def list_verified_queries(
    status: Literal["pending", "certified", "rejected"] | None = Query(None),
    q: str | None = Query(None),
) -> dict[str, Any]:
    """List the verified-query library."""
    rows = dal.list_verified(status=status, search=q)
    users = _user_names(
        {r[k] for r in rows for k in ("created_by", "reviewed_by") if r.get(k)}
    )
    for row in rows:
        row["created_by_name"] = users.get(row["created_by"], row["created_by"])
        row["reviewed_by_name"] = users.get(row["reviewed_by"], row["reviewed_by"])
    return {"data": rows, "count": len(rows)}


@router.post("/verified-queries", status_code=201)
def create_verified_query(body: VerifiedCreate, request: Request) -> dict[str, str]:
    """Add an entry as a reviewer, optionally certifying it at once."""
    try:
        query_id = dal.create_verified(
            question=body.question,
            sql=body.sql,
            database_name=body.database_name,
            note=body.note,
            status=body.status,
            source="manual",
            created_by=resolve_internal_user(request, required=False),
        )
    except dal.PolicyError as exc:
        raise _fail(exc) from exc
    return {"id": query_id}


@router.post("/verified-queries/submit", status_code=201)
def submit_verified_query(body: VerifiedSubmit, request: Request) -> dict[str, str]:
    """Submit a question/SQL pair from answer feedback, for review."""
    try:
        query_id = dal.create_verified(
            question=body.question,
            sql=body.sql,
            database_name=body.database_name,
            note=body.note,
            source="feedback",
            created_by=resolve_internal_user(request, required=False),
        )
    except dal.PolicyError as exc:
        raise _fail(exc) from exc
    return {"id": query_id}


@router.patch("/verified-queries/{query_id}")
def update_verified_query(
    query_id: str, body: VerifiedUpdate, request: Request
) -> dict[str, bool]:
    """Edit an entry, or certify / reject it."""
    try:
        found = dal.update_verified(
            query_id,
            body.model_dump(exclude_unset=True),
            reviewer=resolve_internal_user(request, required=False),
        )
    except dal.PolicyError as exc:
        raise _fail(exc) from exc
    if not found:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"ok": True}


@router.delete("/verified-queries/{query_id}")
def delete_verified_query(query_id: str) -> dict[str, bool]:
    """Delete an entry."""
    if not dal.delete_verified(query_id):
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"ok": True}
