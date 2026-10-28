# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Classify a finished chat question, and rank the ones that went wrong.

Pure functions: the chat router feeds :func:`classify` its final event, and
the board's DAL feeds :func:`build_board` the stored outcomes.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from auto_ontology.dal import schema as s

#: Problems a question can have on the board, worst first. ``downvoted`` comes
#: from the asker's rating, the rest from the outcome itself.
CATEGORY_DOWNVOTED = "downvoted"
CATEGORIES = (
    CATEGORY_DOWNVOTED,
    s.OUTCOME_ERROR,
    s.OUTCOME_NO_SQL,
    s.OUTCOME_EMPTY,
    s.OUTCOME_BLOCKED,
)

#: How many failed questions the board lists.
MAX_GROUPS = 200


@dataclass(frozen=True)
class Outcome:
    outcome: str
    detail: str | None
    sql: str | None


def _rows(answer: dict[str, Any]) -> list[Any] | None:
    """The answer's result rows, or None when it carries none."""
    raw = answer.get("sql_response_from_db")
    if not raw:
        return None
    try:
        rows = json.loads(raw[0]) if isinstance(raw, list) else json.loads(raw)
    except (TypeError, ValueError):
        return None
    return rows if isinstance(rows, list) else None


def classify(
    event: dict[str, Any], audit_decision: str | None, last_sql: str | None
) -> Outcome | None:
    """The outcome of a run from its final ``result`` / ``error`` event."""
    kind = event.get("type")
    if kind == "error":
        message = str(event.get("message") or "")
        blocked = audit_decision == s.AUDIT_BLOCKED or "没有权限" in message
        return Outcome(
            s.OUTCOME_BLOCKED if blocked else s.OUTCOME_ERROR,
            message[:500] or None,
            last_sql,
        )
    if kind != "result":
        return None
    answer = event.get("answer") if isinstance(event.get("answer"), dict) else {}
    response = str(answer.get("response") or "")
    sql = answer.get("sql_code") or None
    if audit_decision == s.AUDIT_BLOCKED or "没有权限" in response:
        return Outcome(s.OUTCOME_BLOCKED, response[:500] or None, sql or last_sql)
    if not sql:
        return Outcome(s.OUTCOME_NO_SQL, response[:500] or None, last_sql)
    rows = _rows(answer)
    if rows is not None and not rows:
        return Outcome(s.OUTCOME_EMPTY, None, sql)
    return Outcome(s.OUTCOME_ANSWERED, None, sql)


_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


def question_key(question: str) -> str:
    """Questions that differ only in case, width, spacing or punctuation match."""
    text = unicodedata.normalize("NFKC", question or "").lower()
    return _PUNCT.sub("", text)


def build_board(
    rows: Iterable[dict[str, Any]],
    dismissed: dict[str, datetime],
) -> dict[str, Any]:
    """Totals and the failed questions, grouped by :func:`question_key`.

    *rows* are outcomes with ``feedback`` joined in; *dismissed* maps a key to
    when an admin marked it handled, which hides failures up to that moment.
    """
    totals = {"questions": 0, "answered": 0, CATEGORY_DOWNVOTED: 0}
    totals.update({c: 0 for c in CATEGORIES if c != CATEGORY_DOWNVOTED})
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        totals["questions"] += 1
        outcome = row["outcome"]
        downvoted = row.get("feedback") == "down"
        if outcome == s.OUTCOME_ANSWERED:
            totals["answered"] += 1
        else:
            totals[outcome] += 1
        if downvoted:
            totals[CATEGORY_DOWNVOTED] += 1
        if outcome == s.OUTCOME_ANSWERED and not downvoted:
            continue
        key = question_key(row["question"])
        if not key:
            continue
        handled = dismissed.get(key)
        if handled is not None and row["created"] <= handled:
            continue
        group = groups.setdefault(
            key,
            {
                "key": key,
                "question": row["question"],
                "count": 0,
                "categories": {},
                "users": set(),
                "sources": set(),
                "last_seen": row["created"],
                "sql": None,
                "detail": None,
                "feedback_note": None,
                "database_name": None,
            },
        )
        group["count"] += 1
        for category in ([CATEGORY_DOWNVOTED] if downvoted else []) + (
            [outcome] if outcome != s.OUTCOME_ANSWERED else []
        ):
            group["categories"][category] = group["categories"].get(category, 0) + 1
        if row.get("user_id"):
            group["users"].add(row["user_id"])
        group["sources"].add(row.get("source") or "app")
        if row["created"] >= group["last_seen"]:
            # The latest wording and evidence describe the group.
            group["last_seen"] = row["created"]
            group["question"] = row["question"]
            group["sql"] = row.get("sql") or group["sql"]
            group["detail"] = row.get("detail") or group["detail"]
            group["feedback_note"] = row.get("feedback_note") or group["feedback_note"]

    def worst(group: dict[str, Any]) -> int:
        return min(CATEGORIES.index(c) for c in group["categories"])

    ranked = sorted(
        groups.values(),
        key=lambda g: (-g["count"], worst(g), -g["last_seen"].timestamp()),
    )[:MAX_GROUPS]
    for group in ranked:
        group["category"] = CATEGORIES[worst(group)]
        group["users"] = len(group["users"])
        group["sources"] = sorted(group["sources"])
        group["last_seen"] = group["last_seen"].isoformat()
    # A downvoted answer still counts as answered: the rate is about getting
    # a result at all, the downvote count says how many were wrong.
    totals["answer_rate"] = (
        round(totals["answered"] / totals["questions"], 4)
        if totals["questions"]
        else None
    )
    return {"totals": totals, "groups": ranked}
