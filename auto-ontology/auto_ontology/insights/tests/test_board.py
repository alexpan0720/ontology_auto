# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
from datetime import datetime, timedelta, timezone

from auto_ontology.dal import schema as s
from auto_ontology.insights.board import build_board, classify, question_key

T0 = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


def _result(sql: str | None, rows: list | None, response: str = "ok") -> dict:
    answer: dict = {"response": response, "sql_code": sql}
    if rows is not None:
        answer["sql_response_from_db"] = [json.dumps(rows)]
    return {"type": "result", "answer": answer}


class TestClassify:
    def test_answered_and_empty(self) -> None:
        assert classify(_result("SELECT 1", [{"a": 1}]), "allowed", None).outcome == (
            s.OUTCOME_ANSWERED
        )
        assert classify(_result("SELECT 1", []), "allowed", None).outcome == (
            s.OUTCOME_EMPTY
        )

    def test_no_sql_keeps_the_last_attempt(self) -> None:
        outcome = classify(_result(None, None, "无法构造查询"), None, "SELECT x")
        assert outcome.outcome == s.OUTCOME_NO_SQL
        assert outcome.sql == "SELECT x"
        assert outcome.detail == "无法构造查询"

    def test_blocked_by_audit_or_message(self) -> None:
        err = {"type": "error", "message": "你没有权限查看以下字段：c.phone"}
        assert classify(err, None, None).outcome == s.OUTCOME_BLOCKED
        assert classify(
            {"type": "error", "message": "boom"}, s.AUDIT_BLOCKED, None
        ).outcome == (s.OUTCOME_BLOCKED)
        assert classify({"type": "error", "message": "boom"}, None, None).outcome == (
            s.OUTCOME_ERROR
        )

    def test_other_events_are_not_outcomes(self) -> None:
        assert classify({"type": "step"}, None, None) is None


def test_question_key_ignores_case_width_and_punctuation() -> None:
    assert question_key("各渠道 GMV？") == question_key("各渠道gmv?")
    assert question_key("ＡＢＣ，１２") == "abc12"


def _row(question: str, outcome: str, minutes: int, **extra: object) -> dict:
    return {
        "question": question,
        "outcome": outcome,
        "created": T0 + timedelta(minutes=minutes),
        "user_id": extra.pop("user_id", "u1"),
        "source": extra.pop("source", "app"),
        **extra,
    }


class TestBoard:
    def test_totals_and_grouping(self) -> None:
        rows = [
            _row("各渠道GMV", s.OUTCOME_ANSWERED, 0),
            _row(
                "各渠道 GMV？",
                s.OUTCOME_ANSWERED,
                1,
                feedback="down",
                feedback_note="少了门店",
            ),
            _row(
                "各渠道gmv",
                s.OUTCOME_ERROR,
                2,
                user_id="u2",
                source="feishu",
                detail="timeout",
            ),
            _row("客户手机号", s.OUTCOME_BLOCKED, 3),
            _row("上月退款", s.OUTCOME_EMPTY, 4),
        ]
        board = build_board(rows, {})
        totals = board["totals"]
        assert totals["questions"] == 5
        assert totals["answered"] == 2
        assert totals["downvoted"] == 1
        assert totals[s.OUTCOME_ERROR] == 1
        assert totals["answer_rate"] == 0.4
        first = board["groups"][0]
        assert first["count"] == 2  # the plain good answer is not a problem
        assert first["category"] == "downvoted"
        assert first["categories"] == {"downvoted": 1, s.OUTCOME_ERROR: 1}
        assert first["users"] == 2
        assert first["sources"] == ["app", "feishu"]
        assert first["question"] == "各渠道gmv"  # latest wording
        assert first["feedback_note"] == "少了门店"
        assert {g["category"] for g in board["groups"]} == {
            "downvoted",
            s.OUTCOME_BLOCKED,
            s.OUTCOME_EMPTY,
        }

    def test_dismissed_until_it_fails_again(self) -> None:
        rows = [_row("上月退款", s.OUTCOME_EMPTY, 0)]
        key = question_key("上月退款")
        assert build_board(rows, {key: T0 + timedelta(minutes=5)})["groups"] == []
        rows.append(_row("上月退款", s.OUTCOME_EMPTY, 10))
        assert (
            build_board(rows, {key: T0 + timedelta(minutes=5)})["groups"][0]["count"]
            == 1
        )

    def test_empty_board(self) -> None:
        board = build_board([], {})
        assert board["totals"]["answer_rate"] is None and board["groups"] == []
