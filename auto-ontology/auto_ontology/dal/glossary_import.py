# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Glossary import batches, their extracted candidates, and applying them.

Accepted candidates are written to the glossary the chat pipeline already reads
(``frontend.acronyms``, see ``server/chat/settings_dal.fetch_acronyms``) and,
when asked, to the description of the business term they match.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import delete, func, insert, select, update

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store
from auto_ontology.infra.postgres import FRONTEND_SCHEMA, get_postgres_connection_string

logger = logging.getLogger(__name__)

#: A batch still "processing" after this long was cut off by a restart.
STALE_AFTER = timedelta(hours=2)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", name or "").casefold()


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------


def create_batch(
    *, file_name: str, chunks_total: int, truncated: bool, created_by: str | None
) -> str:
    rows = store().query_write(
        insert(s.glossary_import)
        .values(
            file_name=file_name,
            chunks_total=chunks_total,
            truncated=truncated,
            created_by=created_by,
        )
        .returning(s.glossary_import.c.id)
    )
    return rows[0]["id"]


def set_progress(batch_id: str, chunks_done: int) -> None:
    store().query_write(
        update(s.glossary_import)
        .where(s.glossary_import.c.id == batch_id)
        .values(chunks_done=chunks_done)
    )


def finish_batch(batch_id: str, candidates: list[dict[str, Any]]) -> None:
    db = store()
    if candidates:
        db.query_write(
            insert(s.glossary_candidate),
            [
                {
                    "import_id": batch_id,
                    "term": c["term"],
                    "definition": c["definition"],
                    "synonyms": c.get("synonyms") or [],
                    "evidence": c.get("evidence"),
                }
                for c in candidates
            ],
        )
    db.query_write(
        update(s.glossary_import)
        .where(s.glossary_import.c.id == batch_id)
        .values(
            status=s.GLOSSARY_IMPORT_DONE, chunks_done=s.glossary_import.c.chunks_total
        )
    )


def fail_batch(batch_id: str, error: str) -> None:
    store().query_write(
        update(s.glossary_import)
        .where(s.glossary_import.c.id == batch_id)
        .values(status=s.GLOSSARY_IMPORT_FAILED, error=error[:500])
    )


def _expire_stale() -> None:
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    store().query_write(
        update(s.glossary_import)
        .where(
            s.glossary_import.c.status == s.GLOSSARY_IMPORT_PROCESSING,
            s.glossary_import.c.created < cutoff,
        )
        .values(
            status=s.GLOSSARY_IMPORT_FAILED, error="提取被中断（服务重启），请重新上传"
        )
    )


def _batch_out(row: dict[str, Any]) -> dict[str, Any]:
    """A batch row as the API returns it.

    The failure text goes out as ``error_message``: the frontend's response
    envelope reserves ``error`` for "this request failed".
    """
    out = {k: v for k, v in row.items() if k != "error"}
    return {**out, "error_message": row["error"], "created": _iso(row["created"])}


def list_batches() -> list[dict[str, Any]]:
    """Every batch, newest first, with its candidates counted by status."""
    _expire_stale()
    counts = store().query_read(
        select(
            s.glossary_candidate.c.import_id,
            s.glossary_candidate.c.status,
            func.count().label("n"),
        ).group_by(s.glossary_candidate.c.import_id, s.glossary_candidate.c.status)
    )
    by_batch: dict[str, dict[str, int]] = {}
    for row in counts:
        by_batch.setdefault(row["import_id"], {})[row["status"]] = row["n"]
    rows = store().query_read(
        select(s.glossary_import).order_by(s.glossary_import.c.created.desc())
    )
    return [
        {
            **_batch_out(row),
            "counts": {
                status: by_batch.get(row["id"], {}).get(status, 0)
                for status in (
                    s.CANDIDATE_PENDING,
                    s.CANDIDATE_ACCEPTED,
                    s.CANDIDATE_REJECTED,
                )
            },
        }
        for row in rows
    ]


def delete_batch(batch_id: str) -> bool:
    rows = store().query_write(
        delete(s.glossary_import)
        .where(s.glossary_import.c.id == batch_id)
        .returning(s.glossary_import.c.id)
    )
    return bool(rows)


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def fetch_glossary() -> dict[str, dict[str, str]]:
    """The current glossary keyed by normalised name."""
    with psycopg.connect(get_postgres_connection_string(), connect_timeout=3) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT name, description FROM {FRONTEND_SCHEMA}.acronyms")
            return {_norm(r["name"]): dict(r) for r in cur.fetchall()}


def _business_terms() -> dict[str, dict[str, Any]]:
    """Semantic terms keyed by normalised name and by each synonym."""
    rows = store().query_read(
        select(
            s.term.c.id, s.term.c.name, s.term.c.description, s.term.c.synonyms
        ).where(s.term.c.source == "semantic")
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
        }
        for name in [row["name"], *(row["synonyms"] or [])]:
            out.setdefault(_norm(name), entry)
    return out


def get_batch(batch_id: str) -> dict[str, Any] | None:
    """A batch with its candidates, each annotated with what it would collide with."""
    _expire_stale()
    rows = store().query_read(
        select(s.glossary_import).where(s.glossary_import.c.id == batch_id)
    )
    if not rows:
        return None
    candidates = store().query_read(
        select(s.glossary_candidate)
        .where(s.glossary_candidate.c.import_id == batch_id)
        .order_by(s.glossary_candidate.c.created, s.glossary_candidate.c.term)
    )
    glossary = fetch_glossary()
    terms = _business_terms()
    annotated = []
    for c in candidates:
        names = [c["term"], *(c["synonyms"] or [])]
        existing = glossary.get(_norm(c["term"]))
        matched = next((terms[_norm(n)] for n in names if _norm(n) in terms), None)
        annotated.append(
            {
                **c,
                "synonyms": list(c["synonyms"] or []),
                "created": _iso(c["created"]),
                "existing_definition": existing["description"] if existing else None,
                "matched_term": matched,
            }
        )
    return {**_batch_out(rows[0]), "candidates": annotated}


def update_candidate(candidate_id: str, changes: dict[str, Any]) -> bool:
    values: dict[str, Any] = {}
    if "term" in changes:
        values["term"] = " ".join((changes["term"] or "").split())
        if not values["term"]:
            raise ValueError("术语不能为空")
    if "definition" in changes:
        values["definition"] = (changes["definition"] or "").strip()
        if not values["definition"]:
            raise ValueError("定义不能为空")
    if "synonyms" in changes:
        values["synonyms"] = [
            " ".join(x.split()) for x in changes["synonyms"] or [] if x and x.strip()
        ]
    if not values:
        return True
    rows = store().query_write(
        update(s.glossary_candidate)
        .where(s.glossary_candidate.c.id == candidate_id)
        .values(**values)
        .returning(s.glossary_candidate.c.id)
    )
    return bool(rows)


def set_status(candidate_ids: list[str], status: str) -> int:
    if not candidate_ids:
        return 0
    rows = store().query_write(
        update(s.glossary_candidate)
        .where(s.glossary_candidate.c.id.in_(candidate_ids))
        .values(status=status)
        .returning(s.glossary_candidate.c.id)
    )
    return len(rows)


def _glossary_text(candidate: dict[str, Any]) -> str:
    """The glossary entry's description: the definition plus its aliases."""
    text = candidate["definition"]
    if candidate["synonyms"]:
        text += f"（别名：{'、'.join(candidate['synonyms'])}）"
    return text


def apply_candidates(
    batch_id: str,
    candidate_ids: list[str],
    *,
    overwrite_existing: bool,
    update_terms: bool,
    modified_by: str | None,
) -> dict[str, int]:
    """Write the chosen candidates to the glossary; returns what happened.

    An entry already in the glossary is replaced only with *overwrite_existing*.
    With *update_terms*, a matched business term gets the definition as its
    description — and its embeddings refreshed, since retrieval reads them.
    """
    batch = get_batch(batch_id)
    if batch is None:
        raise LookupError(batch_id)
    chosen = [
        c
        for c in batch["candidates"]
        if c["id"] in set(candidate_ids) and c["status"] != s.CANDIDATE_ACCEPTED
    ]
    added = replaced = skipped = terms_updated = 0
    accepted: list[str] = []
    with psycopg.connect(get_postgres_connection_string(), connect_timeout=3) as conn:
        with conn.cursor() as cur:
            for c in chosen:
                if c["existing_definition"] is not None and not overwrite_existing:
                    skipped += 1
                    continue
                cur.execute(
                    f"""
                    INSERT INTO {FRONTEND_SCHEMA}.acronyms
                        (id, name, description, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (name) DO UPDATE
                        SET description = EXCLUDED.description, updated_at = NOW()
                    """,
                    (str(uuid.uuid4()), c["term"], _glossary_text(c)),
                )
                if c["existing_definition"] is None:
                    added += 1
                else:
                    replaced += 1
                accepted.append(c["id"])

    if update_terms:
        from auto_ontology.dal import terms as terms_dal
        from auto_ontology.server.terms import service as term_service

        for c in chosen:
            matched = c["matched_term"]
            if not matched or c["id"] not in accepted:
                continue
            terms_dal.update_term(
                matched["id"],
                description=c["definition"],
                modified_by=modified_by,
                touch=True,
            )
            try:
                term_service.refresh_term_embeddings(
                    matched["id"], refresh_dependent_attrs=False
                )
            except Exception:  # noqa: BLE001 - the description is saved regardless
                logger.warning(
                    "Failed to refresh embeddings for term %r",
                    matched["id"],
                    exc_info=True,
                )
            terms_updated += 1

    set_status(accepted, s.CANDIDATE_ACCEPTED)
    return {
        "added": added,
        "replaced": replaced,
        "skipped": skipped,
        "terms_updated": terms_updated,
    }
