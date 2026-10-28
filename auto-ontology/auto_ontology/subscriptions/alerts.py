# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Alert rules over a subscription's result rows.

A result is read as one value per row: the *value column* (chosen, or the
first numeric one) labelled by the first other column, so ``SELECT channel,
COUNT(*) …`` is watched per channel and a single-row ``SELECT SUM(…)`` as one
number. ``threshold`` fires when any value crosses a fixed line; ``change``
when a value moved by at least a percentage since the previous run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from auto_ontology.dal import schema as s

THRESHOLD_OPS = {">": "高于", ">=": "不低于", "<": "低于", "<=": "不高于"}
CHANGE_OPS = {"up": "上涨", "down": "下降", "any": "变动"}


class AlertRuleError(ValueError):
    """An invalid rule; the message is user-facing."""


@dataclass
class AlertResult:
    triggered: bool = False
    lines: list[str] = field(default_factory=list)
    note: str | None = None
    value_column: str | None = None


def validate(alert_type: str, op: str | None, value: float | None) -> None:
    if alert_type == s.ALERT_NONE:
        return
    if alert_type == s.ALERT_THRESHOLD:
        if op not in THRESHOLD_OPS:
            raise AlertRuleError("请选择阈值比较方式")
    elif alert_type == s.ALERT_CHANGE:
        if op not in CHANGE_OPS:
            raise AlertRuleError("请选择变化方向")
        if value is not None and value <= 0:
            raise AlertRuleError("变化幅度应大于 0")
    else:
        raise AlertRuleError("未知的预警类型")
    if value is None or not math.isfinite(value):
        raise AlertRuleError("请填写预警数值")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value.replace(",", ""))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def value_column(rows: list[dict[str, Any]], preferred: str | None) -> str | None:
    if not rows:
        return None
    columns = list(rows[0].keys())
    if preferred:
        match = next((c for c in columns if c.lower() == preferred.lower()), None)
        if match:
            return match
    return next(
        (c for c in columns if any(_number(r.get(c)) is not None for r in rows)), None
    )


def _labelled(rows: list[dict[str, Any]], column: str) -> list[tuple[str, float]]:
    others = [c for c in rows[0].keys() if c != column] if rows else []
    label_column = others[0] if others else None
    out = []
    for row in rows:
        number = _number(row.get(column))
        if number is None:
            continue
        label = str(row.get(label_column)) if label_column else column
        out.append((label, number))
    return out


def fmt(number: float) -> str:
    if number == int(number) and abs(number) < 1e15:
        return f"{int(number):,}"
    return f"{number:,.2f}"


def evaluate(
    rows: list[dict[str, Any]],
    *,
    alert_type: str,
    column: str | None,
    op: str | None,
    value: float | None,
    previous: list[dict[str, Any]] | None,
) -> AlertResult:
    if alert_type == s.ALERT_NONE:
        return AlertResult()
    chosen = value_column(rows, column)
    if chosen is None:
        return AlertResult(note="结果中没有可用于预警的数值列")
    result = AlertResult(value_column=chosen)
    current = _labelled(rows, chosen)
    if alert_type == s.ALERT_THRESHOLD:
        assert op is not None and value is not None
        compare = {
            ">": lambda a: a > value,
            ">=": lambda a: a >= value,
            "<": lambda a: a < value,
            "<=": lambda a: a <= value,
        }[op]
        for label, number in current:
            if compare(number):
                result.lines.append(
                    f"{label}：{fmt(number)}（{THRESHOLD_OPS[op]} {fmt(value)}）"
                )
    else:
        assert op is not None and value is not None
        if not previous:
            result.note = "首次运行，暂无可对比的上次结果"
            return result
        before = dict(_labelled(previous, chosen))
        for label, number in current:
            prior = before.get(label)
            if prior is None or prior == 0:
                continue
            pct = (number - prior) / abs(prior) * 100
            fired = (
                (op == "up" and pct >= value)
                or (op == "down" and pct <= -value)
                or (op == "any" and abs(pct) >= value)
            )
            if fired:
                result.lines.append(
                    f"{label}：{fmt(prior)} → {fmt(number)}（{pct:+.1f}%）"
                )
    result.triggered = bool(result.lines)
    return result


def describe(
    alert_type: str, column: str | None, op: str | None, value: float | None
) -> str:
    """The rule in words, e.g. ``退款率 高于 5``."""
    if alert_type == s.ALERT_NONE or op is None or value is None:
        return "不预警"
    subject = column or "数值"
    if alert_type == s.ALERT_THRESHOLD:
        return f"{subject} {THRESHOLD_OPS.get(op, op)} {fmt(value)}"
    return f"{subject} 较上次{CHANGE_OPS.get(op, op)} ≥ {fmt(value)}%"
