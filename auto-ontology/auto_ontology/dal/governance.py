# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Access policies, the access audit trail, and the verified-query library.

:func:`resolve_access` is the one place a user's policies are worked out; the
chat router calls it per question and hands the result to the worker, where
``auto_ontology.governance.enforce`` applies it to every statement.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from sqlalchemy import delete, func, insert, or_, select, update

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store, write_transaction
from auto_ontology.governance.enforce import (
    MASK_STYLES,
    AccessContext,
    ColumnRule,
    MaskRule,
    RowRule,
    detect_mask_style,
    validate_predicate,
)

logger = logging.getLogger(__name__)


class PolicyError(ValueError):
    """A policy write the caller has to fix; the message is user-facing."""


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def _policy_select():
    return select(
        s.access_policy.c.id,
        s.access_policy.c.kind,
        s.access_policy.c.table_id,
        s.access_policy.c.column_name,
        s.access_policy.c.predicate,
        s.access_policy.c.mask_style,
        s.access_policy.c.group_ids,
        s.access_policy.c.description,
        s.access_policy.c.enabled,
        s.access_policy.c.created_by,
        s.access_policy.c.created,
        s.catalog_table.c.name.label("table_name"),
        s.catalog_schema.c.name.label("schema_name"),
        s.catalog_database.c.name.label("database_name"),
        s.catalog_database.c.dialect.label("dialect"),
    ).select_from(
        s.access_policy.join(
            s.catalog_table, s.catalog_table.c.id == s.access_policy.c.table_id
        )
        .join(s.catalog_schema, s.catalog_schema.c.id == s.catalog_table.c.schema_id)
        .join(
            s.catalog_database,
            s.catalog_database.c.id == s.catalog_schema.c.database_id,
        )
    )


def _group_names() -> dict[str, str]:
    rows = store().query_read(select(s.user_group.c.id, s.user_group.c.name))
    return {row["id"]: row["name"] for row in rows}


def list_policies() -> list[dict[str, Any]]:
    """Every policy with its table's names and its groups' names."""
    names = _group_names()
    rows = store().query_read(
        _policy_select().order_by(
            s.catalog_table.c.name, s.access_policy.c.kind, s.access_policy.c.created
        )
    )
    return [
        {
            **row,
            "group_ids": list(row["group_ids"] or []),
            "group_names": [names.get(g, g) for g in row["group_ids"] or []],
            # What the mask policy applies when no style was chosen by hand.
            "effective_mask_style": (
                row["mask_style"] or detect_mask_style(row["column_name"])
            )
            if row["kind"] == s.ACCESS_POLICY_MASK
            else None,
            "created": row["created"].isoformat() if row["created"] else None,
        }
        for row in rows
    ]


def _table_info(table_id: str) -> dict[str, Any]:
    rows = store().query_read(
        select(
            s.catalog_table.c.id,
            s.catalog_database.c.dialect,
        )
        .select_from(
            s.catalog_table.join(
                s.catalog_schema, s.catalog_schema.c.id == s.catalog_table.c.schema_id
            ).join(
                s.catalog_database,
                s.catalog_database.c.id == s.catalog_schema.c.database_id,
            )
        )
        .where(s.catalog_table.c.id == table_id)
    )
    if not rows:
        raise PolicyError("数据表不存在")
    return rows[0]


def _column_exists(table_id: str, column_name: str) -> bool:
    rows = store().query_read(
        select(s.catalog_column.c.id).where(
            s.catalog_column.c.table_id == table_id,
            func.lower(s.catalog_column.c.name) == column_name.strip().lower(),
        )
    )
    return bool(rows)


def _check_groups(group_ids: list[str]) -> list[str]:
    group_ids = sorted({g for g in group_ids if g})
    unknown = set(group_ids) - set(_group_names())
    if unknown:
        raise PolicyError("包含不存在的用户组")
    return group_ids


def _validated(
    kind: str,
    table_id: str,
    column_name: str | None,
    predicate: str | None,
) -> tuple[str | None, str | None]:
    info = _table_info(table_id)
    if kind in (s.ACCESS_POLICY_COLUMN, s.ACCESS_POLICY_MASK):
        column_name = (column_name or "").strip()
        if not column_name or not _column_exists(table_id, column_name):
            raise PolicyError("请选择该表中存在的字段")
        return column_name, None
    if kind == s.ACCESS_POLICY_ROW:
        predicate = (predicate or "").strip()
        if not predicate:
            raise PolicyError("请填写行过滤条件")
        problem = validate_predicate(predicate, info["dialect"])
        if problem:
            raise PolicyError(problem)
        return None, predicate
    raise PolicyError("未知的策略类型")


def _mask_style(kind: str, style: str | None) -> str | None:
    """A mask policy's style; None picks one from the column name when applied."""
    if kind != s.ACCESS_POLICY_MASK or not style:
        return None
    if style not in MASK_STYLES:
        raise PolicyError("未知的脱敏方式")
    return style


def create_policy(
    *,
    kind: str,
    table_id: str,
    column_name: str | None = None,
    predicate: str | None = None,
    mask_style: str | None = None,
    group_ids: list[str] | None = None,
    description: str | None = None,
    enabled: bool = True,
    created_by: str | None = None,
) -> str:
    column_name, predicate = _validated(kind, table_id, column_name, predicate)
    rows = store().query_write(
        insert(s.access_policy)
        .values(
            kind=kind,
            table_id=table_id,
            column_name=column_name,
            predicate=predicate,
            mask_style=_mask_style(kind, mask_style),
            group_ids=_check_groups(group_ids or []),
            description=(description or "").strip() or None,
            enabled=enabled,
            created_by=created_by,
        )
        .returning(s.access_policy.c.id)
    )
    return rows[0]["id"]


def update_policy(policy_id: str, changes: dict[str, Any]) -> bool:
    """Apply *changes* (any of the create fields but ``kind``/``table_id``)."""
    current = store().query_read(
        select(s.access_policy).where(s.access_policy.c.id == policy_id)
    )
    if not current:
        return False
    row = current[0]
    values: dict[str, Any] = {}
    if "column_name" in changes or "predicate" in changes:
        column_name, predicate = _validated(
            row["kind"],
            row["table_id"],
            changes.get("column_name", row["column_name"]),
            changes.get("predicate", row["predicate"]),
        )
        values.update(column_name=column_name, predicate=predicate)
    if "mask_style" in changes:
        values["mask_style"] = _mask_style(row["kind"], changes["mask_style"])
    if "group_ids" in changes:
        values["group_ids"] = _check_groups(changes["group_ids"] or [])
    if "description" in changes:
        values["description"] = (changes["description"] or "").strip() or None
    if "enabled" in changes:
        values["enabled"] = bool(changes["enabled"])
    if values:
        store().query_write(
            update(s.access_policy)
            .where(s.access_policy.c.id == policy_id)
            .values(**values)
        )
    return True


def delete_policy(policy_id: str) -> bool:
    rows = store().query_write(
        delete(s.access_policy)
        .where(s.access_policy.c.id == policy_id)
        .returning(s.access_policy.c.id)
    )
    return bool(rows)


def is_key_column(name: str) -> bool:
    """Whether a column looks like an identifier (``id``, ``customer_id``, ``orderId``).

    Masking one would break joins: different keys collapse to the same masked
    value (``C***1``), so a join across masked keys silently pairs wrong rows.
    """
    return name.lower() == "id" or name.lower().endswith("_id") or name.endswith("Id")


def restrict_pii_columns(created_by: str | None = None) -> tuple[int, int]:
    """A mask policy for every PII-tagged column with no policy.

    Masking rather than refusing: the column stays usable for counting and
    grouping, and an admin who wants it refused outright can switch that one
    column to a column policy. Identifier columns are left alone (see
    :func:`is_key_column`); an admin can still add a policy for one by hand.
    Returns ``(created, skipped_keys)``.
    """
    from auto_ontology.dal.tags import PII_TAG_NAME

    tagged = store().query_read(
        select(
            s.catalog_column.c.table_id,
            s.catalog_column.c.name.label("column_name"),
        )
        .select_from(
            s.tag_target.join(s.tag, s.tag.c.id == s.tag_target.c.tag_id).join(
                s.catalog_column, s.catalog_column.c.id == s.tag_target.c.column_id
            )
        )
        .where(s.tag.c.name == PII_TAG_NAME)
    )
    existing = {
        (row["table_id"], (row["column_name"] or "").lower())
        for row in store().query_read(
            select(s.access_policy.c.table_id, s.access_policy.c.column_name).where(
                s.access_policy.c.kind.in_(
                    (s.ACCESS_POLICY_COLUMN, s.ACCESS_POLICY_MASK)
                )
            )
        )
    }
    created = skipped_keys = 0
    with write_transaction():
        for row in tagged:
            key = (row["table_id"], row["column_name"].lower())
            if key in existing:
                continue
            if is_key_column(row["column_name"]):
                skipped_keys += 1
                continue
            existing.add(key)
            store().query_write(
                insert(s.access_policy).values(
                    kind=s.ACCESS_POLICY_MASK,
                    table_id=row["table_id"],
                    column_name=row["column_name"],
                    group_ids=[],
                    description="由敏感信息（PII）标签自动生成的脱敏策略",
                    created_by=created_by,
                )
            )
            created += 1
    return created, skipped_keys


# ---------------------------------------------------------------------------
# Resolving a user's access
# ---------------------------------------------------------------------------


def _user_groups(user_id: str) -> list[dict[str, Any]]:
    return store().query_read(
        select(s.user_group.c.id, s.user_group.c.role)
        .select_from(
            s.user_group__member.join(
                s.user_group, s.user_group.c.id == s.user_group__member.c.group_id
            )
        )
        .where(s.user_group__member.c.user_id == user_id)
    )


def resolve_access(user_id: str | None) -> AccessContext:
    """The policies that bind *user_id* for one chat question.

    An unknown caller (no identity forwarded) is treated as a user in no
    groups: the strictest reading, never the most permissive.
    """
    from auto_ontology.server.users.postgres_dal import get_user_role

    groups: list[dict[str, Any]] = []
    if user_id:
        groups = _user_groups(user_id)
        if get_user_role(user_id) == s.GROUP_ROLE_ADMIN or any(
            g["role"] == s.GROUP_ROLE_ADMIN for g in groups
        ):
            return AccessContext(is_admin=True)
    member_of = {g["id"] for g in groups}

    policies = store().query_read(
        _policy_select().where(s.access_policy.c.enabled.is_(True))
    )

    columns: list[ColumnRule] = []
    masks: list[dict[str, Any]] = []
    rows_by_table: dict[str, dict[str, Any]] = {}
    for p in policies:
        applies_to = set(p["group_ids"] or [])
        location = {
            "database": p["database_name"],
            "schema": p["schema_name"],
            "table": p["table_name"],
        }
        if p["kind"] == s.ACCESS_POLICY_COLUMN:
            # Allowed groups may read the column; everyone else may not.
            if not (applies_to & member_of):
                columns.append(
                    ColumnRule(policy_id=p["id"], column=p["column_name"], **location)
                )
            continue
        if p["kind"] == s.ACCESS_POLICY_MASK:
            # Exempt groups see the real value; everyone else the masked one.
            if not (applies_to & member_of):
                masks.append({**p, "location": location})
            continue
        entry = rows_by_table.setdefault(
            p["table_id"], {**location, "predicates": [], "policy_ids": []}
        )
        entry["policy_ids"].append(p["id"])
        if not applies_to or applies_to & member_of:
            entry["predicates"].append(p["predicate"])

    rows = [
        RowRule(
            policy_ids=tuple(sorted(e["policy_ids"])),
            database=e["database"],
            schema=e["schema"],
            table=e["table"],
            predicate=" OR ".join(f"({p})" for p in e["predicates"])
            if e["predicates"]
            else None,
        )
        for e in rows_by_table.values()
    ]
    table_columns = _ordered_columns({m["table_id"] for m in masks})
    mask_rules = [
        MaskRule(
            policy_id=m["id"],
            column=m["column_name"],
            style=m["mask_style"] or detect_mask_style(m["column_name"]),
            columns=tuple(table_columns.get(m["table_id"], ())),
            **m["location"],
        )
        for m in masks
    ]
    return AccessContext(is_admin=False, columns=columns, rows=rows, masks=mask_rules)


def _ordered_columns(table_ids: set[str]) -> dict[str, list[str]]:
    """Each table's column names in their source order."""
    if not table_ids:
        return {}
    rows = store().query_read(
        select(s.catalog_column.c.table_id, s.catalog_column.c.name)
        .where(s.catalog_column.c.table_id.in_(sorted(table_ids)))
        .order_by(
            s.catalog_column.c.table_id,
            s.catalog_column.c.ordinal_position.nulls_last(),
            s.catalog_column.c.name,
        )
    )
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(row["table_id"], []).append(row["name"])
    return out


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def record_audit(
    *,
    user_id: str | None,
    conversation_id: str | None,
    question: str | None,
    sql: str | None,
    decision: str,
    reason: str | None,
    policy_ids: list[str],
    statements: list[dict[str, Any]],
) -> None:
    store().query_write(
        insert(s.access_audit).values(
            user_id=user_id,
            conversation_id=conversation_id,
            question=question,
            sql=sql,
            decision=decision,
            reason=reason or None,
            policy_ids=policy_ids,
            statements=statements,
        )
    )


def list_audit(
    *,
    user_id: str | None = None,
    decision: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    conditions = []
    if user_id:
        conditions.append(s.access_audit.c.user_id == user_id)
    if decision:
        conditions.append(s.access_audit.c.decision == decision)
    if search and search.strip():
        needle = f"%{search.strip()}%"
        conditions.append(
            or_(
                s.access_audit.c.question.ilike(needle),
                s.access_audit.c.sql.ilike(needle),
            )
        )
    total = store().query_read(
        select(func.count().label("n")).select_from(s.access_audit).where(*conditions)
    )[0]["n"]
    rows = store().query_read(
        select(s.access_audit)
        .where(*conditions)
        .order_by(s.access_audit.c.created.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 500))
    )
    return {
        "count": total,
        "data": [
            {
                **row,
                "policy_ids": list(row["policy_ids"] or []),
                "created": row["created"].isoformat() if row["created"] else None,
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# Verified queries
# ---------------------------------------------------------------------------


def _embed(question: str) -> list[float] | None:
    """The question's embedding, or None when the endpoint is unavailable.

    A missing embedding only keeps the entry out of similarity search until it
    is edited again; it never blocks saving what a reviewer vouched for.
    """
    try:
        from auto_ontology.utils.embedding import embed_texts, get_embed_params

        vectors = embed_texts(
            [question], get_embed_params(), "query", timeout=60.0, retries=1
        )
        return vectors[0]
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("Embedding a verified question failed")
        return None


def _verified_public(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if k != "embedding"}
    for key in ("created", "reviewed"):
        out[key] = row[key].isoformat() if row.get(key) else None
    out["has_embedding"] = bool(row.get("embedding"))
    return out


def list_verified(
    *, status: str | None = None, search: str | None = None
) -> list[dict[str, Any]]:
    conditions = []
    if status:
        conditions.append(s.verified_query.c.status == status)
    if search and search.strip():
        needle = f"%{search.strip()}%"
        conditions.append(
            or_(
                s.verified_query.c.question.ilike(needle),
                s.verified_query.c.sql.ilike(needle),
            )
        )
    rows = store().query_read(
        select(s.verified_query)
        .where(*conditions)
        .order_by(s.verified_query.c.created.desc())
    )
    return [_verified_public(r) for r in rows]


def create_verified(
    *,
    question: str,
    sql: str,
    database_name: str | None,
    source: str,
    note: str | None,
    created_by: str | None,
    status: str = s.VERIFIED_PENDING,
) -> str:
    question, sql = question.strip(), sql.strip()
    if not question or not sql:
        raise PolicyError("问题和 SQL 都不能为空")
    rows = store().query_write(
        insert(s.verified_query)
        .values(
            question=question,
            sql=sql,
            database_name=(database_name or "").strip() or None,
            source=source,
            note=(note or "").strip() or None,
            status=status,
            embedding=_embed(question),
            created_by=created_by,
            reviewed_by=created_by if status != s.VERIFIED_PENDING else None,
            reviewed=func.now() if status != s.VERIFIED_PENDING else None,
        )
        .returning(s.verified_query.c.id)
    )
    return rows[0]["id"]


def update_verified(
    query_id: str, changes: dict[str, Any], reviewer: str | None
) -> bool:
    current = store().query_read(
        select(s.verified_query.c.id).where(s.verified_query.c.id == query_id)
    )
    if not current:
        return False
    values: dict[str, Any] = {}
    if "question" in changes:
        question = (changes["question"] or "").strip()
        if not question:
            raise PolicyError("问题不能为空")
        values.update(question=question, embedding=_embed(question))
    if "sql" in changes:
        sql = (changes["sql"] or "").strip()
        if not sql:
            raise PolicyError("SQL 不能为空")
        values["sql"] = sql
    if "database_name" in changes:
        values["database_name"] = (changes["database_name"] or "").strip() or None
    if "note" in changes:
        values["note"] = (changes["note"] or "").strip() or None
    if "status" in changes:
        status = changes["status"]
        if status not in (
            s.VERIFIED_PENDING,
            s.VERIFIED_CERTIFIED,
            s.VERIFIED_REJECTED,
        ):
            raise PolicyError("未知的状态")
        values.update(status=status, reviewed_by=reviewer, reviewed=func.now())
    if values:
        store().query_write(
            update(s.verified_query)
            .where(s.verified_query.c.id == query_id)
            .values(**values)
        )
    return True


def delete_verified(query_id: str) -> bool:
    rows = store().query_write(
        delete(s.verified_query)
        .where(s.verified_query.c.id == query_id)
        .returning(s.verified_query.c.id)
    )
    return bool(rows)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def find_similar_verified(
    question: str,
    database_name: str | None = None,
    *,
    limit: int = 3,
    min_score: float = 0.6,
) -> list[dict[str, Any]]:
    """Certified entries most similar to *question*, best first, with ``score``.

    Restricted to *database_name* when given (plus entries with no database).
    """
    conditions = [
        s.verified_query.c.status == s.VERIFIED_CERTIFIED,
        s.verified_query.c.embedding.is_not(None),
    ]
    if database_name:
        conditions.append(
            or_(
                func.lower(s.verified_query.c.database_name) == database_name.lower(),
                s.verified_query.c.database_name.is_(None),
            )
        )
    candidates = store().query_read(
        select(
            s.verified_query.c.id,
            s.verified_query.c.question,
            s.verified_query.c.sql,
            s.verified_query.c.database_name,
            s.verified_query.c.embedding,
        ).where(*conditions)
    )
    if not candidates:
        return []
    vector = _embed(question)
    if vector is None:
        return []
    scored = [
        {
            "id": c["id"],
            "question": c["question"],
            "sql": c["sql"],
            "database_name": c["database_name"],
            "score": round(_cosine(vector, list(c["embedding"])), 4),
        }
        for c in candidates
    ]
    scored = [c for c in scored if c["score"] >= min_score]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:limit]
