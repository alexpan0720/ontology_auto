# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run a subscription: query under its policies, check its rule, push, record.

The SQL goes through the same policy layer as a chat question
(:class:`~auto_ontology.governance.enforce.PolicyEnforcingConnector`) as the
subscription's ``run_as_user_id`` — null meaning a user in no groups — and is
written to the access audit, so a push can never show a group chat more than
its configured identity may see.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from zoneinfo import ZoneInfo

import sqlglot
from sqlglot import exp

from auto_ontology.dal import schema as s
from auto_ontology.dal import subscriptions as dal
from auto_ontology.subscriptions import alerts, push
from auto_ontology.subscriptions.schedule import describe as describe_schedule

logger = logging.getLogger(__name__)

#: Rows listed in a pushed message.
MESSAGE_ROWS = 15


class RunError(RuntimeError):
    """The query could not run; the message is user-facing."""


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    columns: list[str]


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()  # numpy scalars
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def check_read_only(sql: str, dialect: str | None) -> None:
    """Refuse anything but one SELECT: a subscription only ever reads."""
    try:
        statements = [t for t in sqlglot.parse(sql, read=dialect or None) if t]
    except sqlglot.errors.ParseError as exc:
        raise RunError(f"SQL 无法解析：{exc}") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise RunError("订阅只能使用一条 SELECT 查询")


def _connector(database_name: str | None) -> Any:
    from auto_ontology.connectors import get_connectors

    connectors = get_connectors()
    if database_name:
        connectors = [
            c for c in connectors if getattr(c, "database_name", None) == database_name
        ]
    if not connectors:
        raise RunError(
            f"找不到数据库连接：{database_name}"
            if database_name
            else "还没有数据库连接"
        )
    if len(connectors) > 1:
        raise RunError("有多个数据库连接，请为订阅指定数据库")
    return connectors[0]


def run_query(
    sql: str, database_name: str | None, user_id: str | None, label: str
) -> QueryResult:
    """*sql* as *user_id* would see it; audited like a chat question."""
    from auto_ontology.dal.governance import record_audit, resolve_access
    from auto_ontology.governance.enforce import (
        AccessDeniedError,
        PolicyEnforcingConnector,
        summarize,
    )

    connector = _connector(database_name)
    check_read_only(sql, connector.dialect)
    log: list[dict[str, Any]] = []
    wrapped = PolicyEnforcingConnector(connector, resolve_access(user_id), log)
    try:
        frame = wrapped.execute(sql)
    except AccessDeniedError as exc:
        raise RunError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - the database's message is the help
        raise RunError(f"查询失败：{exc}") from exc
    finally:
        if log:
            verdict = summarize(log)
            try:
                record_audit(
                    user_id=user_id,
                    conversation_id=None,
                    question=label,
                    sql=sql,
                    decision=verdict["decision"],
                    reason=verdict["reason"],
                    policy_ids=verdict["policy_ids"],
                    statements=verdict["statements"],
                )
            except Exception:  # noqa: BLE001 - auditing must not hide the result
                logger.exception("Failed to audit subscription query")
    columns = [str(c) for c in frame.columns]
    rows = [
        {col: _json_value(v) for col, v in zip(columns, record)}
        for record in frame.itertuples(index=False, name=None)
    ]
    return QueryResult(rows=rows, columns=columns)


def _cell(value: Any) -> str:
    if isinstance(value, float):
        return alerts.fmt(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return "—" if value is None else str(value)


def format_message(
    sub: dict[str, Any],
    rows: list[dict[str, Any]],
    alert: alerts.AlertResult,
    when: datetime,
) -> tuple[str, str]:
    """Title and markdown body of a push, readable in both chat apps."""
    local = when.astimezone(ZoneInfo(sub.get("timezone") or "Asia/Shanghai"))
    title = f"⚠️ 预警：{sub['name']}" if alert.triggered else sub["name"]
    parts = [
        f"{local:%Y-%m-%d %H:%M} · {describe_schedule(sub['schedule'], sub['time_of_day'], sub.get('weekday'))}"
    ]
    if alert.triggered:
        rule = alerts.describe(
            sub["alert_type"],
            alert.value_column,
            sub.get("alert_op"),
            sub.get("alert_value"),
        )
        parts.append(f"**触发预警（{rule}）**")
        parts.extend(f"- {line}" for line in alert.lines[:MESSAGE_ROWS])
    if rows:
        parts.append("**最新结果**")
        for row in rows[:MESSAGE_ROWS]:
            parts.append("- " + "｜".join(f"{k}：{_cell(v)}" for k, v in row.items()))
        if len(rows) > MESSAGE_ROWS:
            parts.append(f"（共 {len(rows)} 行，仅显示前 {MESSAGE_ROWS} 行）")
    else:
        parts.append("查询没有返回数据。")
    who = "指定用户" if sub.get("run_as_user_id") else "普通用户（无用户组）"
    parts.append(f"<font color='grey'>来自 alexpan 本体 · 按{who}的数据权限查询</font>")
    return title, "\n\n".join(parts)


def evaluate(
    sub: dict[str, Any],
    rows: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None,
) -> alerts.AlertResult:
    return alerts.evaluate(
        rows,
        alert_type=sub["alert_type"],
        column=sub.get("alert_column"),
        op=sub.get("alert_op"),
        value=sub.get("alert_value"),
        previous=previous,
    )


def execute(
    subscription_id: str,
    *,
    trigger: str,
    query: Callable[..., QueryResult] = run_query,
    sender: Callable[..., push.Delivery] = push.send,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Run one subscription now and record the run."""
    sub = dal.get_subscription(subscription_id)
    if sub is None:
        raise RunError("订阅不存在")
    previous = dal.previous_rows(subscription_id)
    try:
        result = query(
            sub["sql"],
            sub["database_name"],
            sub["run_as_user_id"],
            f"[订阅] {sub['name']}",
        )
    except RunError as exc:
        return dal.record_run(
            subscription_id=subscription_id,
            trigger=trigger,
            status=s.RUN_FAILED,
            alerted=False,
            summary=str(exc),
            rows=None,
            deliveries=[],
        )
    alert = evaluate(sub, result.rows, previous)
    quiet = sub["push_mode"] == s.PUSH_ON_ALERT and not alert.triggered
    deliveries: list[dict[str, Any]] = []
    if not quiet:
        title, body = format_message(sub, result.rows, alert, now())
        for channel in dal.get_channels(list(sub["channel_ids"] or [])):
            delivery = sender(channel, title, body, alert=alert.triggered)
            deliveries.append(
                {
                    "channel_id": channel["id"],
                    "name": channel["name"],
                    "ok": delivery.ok,
                    "detail": delivery.detail,
                }
            )
    if quiet:
        summary = alert.note or "未触发预警，本次不推送"
        status = s.RUN_QUIET
    elif not deliveries:
        summary = "没有可用的推送渠道"
        status = s.RUN_FAILED
    elif all(d["ok"] for d in deliveries):
        summary = (
            "触发预警，" if alert.triggered else ""
        ) + f"已推送到 {len(deliveries)} 个群"
        status = s.RUN_SENT
    else:
        failed = [d for d in deliveries if not d["ok"]]
        summary = "；".join(f"{d['name']}：{d['detail']}" for d in failed)
        status = s.RUN_FAILED if len(failed) == len(deliveries) else s.RUN_SENT
    if alert.note and not quiet:
        summary = f"{summary}（{alert.note}）"
    return dal.record_run(
        subscription_id=subscription_id,
        trigger=trigger,
        status=status,
        alerted=alert.triggered,
        summary=summary,
        rows=result.rows,
        deliveries=deliveries,
    )


def preview(
    fields: dict[str, Any], subscription_id: str | None = None
) -> dict[str, Any]:
    """Run unsaved settings without pushing: the rows, and whether the rule fires."""
    result = run_query(
        fields["sql"],
        fields.get("database_name"),
        fields.get("run_as_user_id"),
        "[订阅试运行]",
    )
    previous = dal.previous_rows(subscription_id) if subscription_id else None
    alert = alerts.evaluate(
        result.rows,
        alert_type=fields.get("alert_type") or s.ALERT_NONE,
        column=fields.get("alert_column"),
        op=fields.get("alert_op"),
        value=fields.get("alert_value"),
        previous=previous,
    )
    sub = {
        "timezone": "Asia/Shanghai",
        "time_of_day": "09:00",
        "weekday": None,
        **fields,
    }
    sub.setdefault("name", "预览")
    title, body = format_message(sub, result.rows, alert, datetime.now(timezone.utc))
    return {
        "columns": result.columns,
        "rows": result.rows[:50],
        "row_count": len(result.rows),
        "alert": {
            "triggered": alert.triggered,
            "lines": alert.lines,
            "note": alert.note,
            "value_column": alert.value_column,
        },
        "message": {"title": title, "body": body},
    }
