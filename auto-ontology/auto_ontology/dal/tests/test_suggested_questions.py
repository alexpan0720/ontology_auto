# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Suggested questions: certified only, each wording once, newest review first.

Needs a migrated database and skips without one. Other certified questions in
the store are ignored by filtering on this test's own prefix.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from auto_ontology.dal import governance as dal  # noqa: E402
from auto_ontology.dal import schema as s  # noqa: E402
from auto_ontology.dal.session import store  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def require_schema():
    if not os.environ.get("POSTGRES_USER"):
        pytest.skip("POSTGRES_* not set")
    try:
        store().query_read("SELECT 1 FROM verified_query LIMIT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"auto_ontology schema unavailable (alembic upgrade head): {exc}")


@pytest.fixture
def prefix():
    value = f"sq-{uuid.uuid4().hex[:8]}"
    yield value
    store().query_write(
        s.verified_query.delete().where(s.verified_query.c.question.like(f"{value}%"))
    )


def _add(question: str, status: str, reviewed_minutes_ago: int | None) -> None:
    reviewed = (
        datetime.now(timezone.utc) - timedelta(minutes=reviewed_minutes_ago)
        if reviewed_minutes_ago is not None
        else None
    )
    store().query_write(
        s.verified_query.insert().values(
            question=question, sql="SELECT 1", status=status, reviewed=reviewed
        )
    )


def _mine(prefix: str) -> list[str]:
    return [
        row["question"]
        for row in dal.suggested_questions(1000)
        if row["question"].startswith(prefix)
    ]


def test_only_certified_questions_are_suggested_newest_review_first(prefix) -> None:
    _add(f"{prefix} 上月 GMV", s.VERIFIED_CERTIFIED, 30)
    _add(f"{prefix} 各渠道订单数", s.VERIFIED_CERTIFIED, 5)
    _add(f"{prefix} 待审的问题", s.VERIFIED_PENDING, None)
    _add(f"{prefix} 被拒的问题", s.VERIFIED_REJECTED, 1)

    assert _mine(prefix) == [f"{prefix} 各渠道订单数", f"{prefix} 上月 GMV"]


def test_the_same_wording_is_suggested_once(prefix) -> None:
    _add(f"{prefix} GMV 复购率", s.VERIFIED_CERTIFIED, 10)
    _add(f"{prefix} gmv 复购率 ", s.VERIFIED_CERTIFIED, 20)

    assert _mine(prefix) == [f"{prefix} GMV 复购率"]


def test_suggestions_carry_no_sql(prefix) -> None:
    _add(f"{prefix} 客单价", s.VERIFIED_CERTIFIED, 1)
    (row,) = [
        r for r in dal.suggested_questions(1000) if r["question"].startswith(prefix)
    ]
    assert set(row) == {"id", "question"}


def test_the_limit_is_respected() -> None:
    assert len(dal.suggested_questions(1)) <= 1
