# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Question outcomes and the questions an admin marked handled on the board."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store
from auto_ontology.infra.postgres import FRONTEND_SCHEMA, get_postgres_connection_string

#: The board never reads more outcomes than this, newest first.
MAX_ROWS = 20000


def record_outcome(
    *,
    user_id: str | None,
    source: str,
    question: str,
    outcome: str,
    sql: str | None,
    detail: str | None,
    message_id: str | None,
) -> None:
    store().query_write(
        insert(s.question_outcome).values(
            user_id=user_id,
            source=source or "app",
            question=question,
            outcome=outcome,
            sql=sql,
            detail=detail,
            message_id=message_id,
        )
    )


def _feedback(message_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Each answer's rating, from the chat's own message table."""
    if not message_ids:
        return {}
    with psycopg.connect(get_postgres_connection_string(), connect_timeout=3) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id::text AS id, feedback, feedback_note "
                f"FROM {FRONTEND_SCHEMA}.messages WHERE id::text = ANY(%s)",
                (message_ids,),
            )
            return {r["id"]: r for r in cur.fetchall()}


def list_outcomes(days: int) -> list[dict[str, Any]]:
    """The last *days* of outcomes, each with its answer's rating joined in."""
    since = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    rows = store().query_read(
        select(s.question_outcome)
        .where(s.question_outcome.c.created >= since)
        .order_by(s.question_outcome.c.created.desc())
        .limit(MAX_ROWS)
    )
    ratings = _feedback([r["message_id"] for r in rows if r["message_id"]])
    out = []
    for row in rows:
        rating = ratings.get(row["message_id"] or "") or {}
        out.append(
            {
                **row,
                "feedback": rating.get("feedback"),
                "feedback_note": rating.get("feedback_note"),
            }
        )
    return out


def dismissals() -> dict[str, datetime]:
    rows = store().query_read(select(s.insight_dismissal))
    return {r["question_key"]: r["created"] for r in rows}


def dismiss(question_key: str, user_id: str | None) -> None:
    statement = pg_insert(s.insight_dismissal).values(
        question_key=question_key, dismissed_by=user_id
    )
    store().query_write(
        statement.on_conflict_do_update(
            index_elements=[s.insight_dismissal.c.question_key],
            set_={"dismissed_by": user_id, "created": datetime.now(timezone.utc)},
        )
    )


def undismiss(question_key: str) -> bool:
    rows = store().query_write(
        delete(s.insight_dismissal)
        .where(s.insight_dismissal.c.question_key == question_key)
        .returning(s.insight_dismissal.c.question_key)
    )
    return bool(rows)
