# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Platform-neutral half of the bots: ask the chat API, format the answer.

A bot never queries a database itself. It calls the same chat endpoint the web
UI uses, as the account its sender's email maps to, so access policies, masking
and the access audit apply exactly as they do in the browser. A sender with no
matching account asks as a caller with no groups — the strictest reading.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import httpx

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("BOT_BACKEND_URL", "http://auto-ontology:3001").rstrip("/")
#: A question runs the whole text-to-SQL pipeline; a few minutes is generous.
ASK_TIMEOUT_S = 300.0
#: Rows of the result shown in a chat message; the rest are counted, not sent.
MAX_ROWS = 15
#: Characters of answer text kept, so a reply stays within IM message limits.
MAX_TEXT = 3500

HELP_TEXT = (
    "你好，我是 alexpan 本体问数助手。直接用自然语言提问即可，例如：\n"
    "- 2026 年每个月已完成订单的销售额是多少？\n"
    "- 哪个品类的毛利率最高？\n"
    "群聊中请 @我 提问。查询会按你的账号权限执行。"
)


@dataclass
class Asker:
    """Who is asking: the mapped account, or a platform id when there is none."""

    platform: str
    platform_user_id: str
    user_id: str | None
    display: str

    @property
    def identity(self) -> str:
        """The id the chat API records in the audit trail."""
        return self.user_id or f"{self.platform}:{self.platform_user_id}"


# A mention starts a token (``@机器人``, Feishu's ``@_user_1``); an ``@`` inside
# a word, as in an email address in the question, is left alone.
_MENTION_RE = re.compile(r"@_user_\d+|(?<!\S)@\S+")


def clean_question(text: str, mention_names: Iterable[str] = ()) -> str:
    """The question without @mentions of the bot (or anyone) and extra spacing."""
    for name in mention_names:
        if name:
            text = text.replace(f"@{name}", " ")
    text = _MENTION_RE.sub(" ", text)
    return " ".join(text.split())


def find_user_by_email(email: str | None) -> str | None:
    """The account id whose email is *email* (case-insensitive), if any."""
    if not email:
        return None
    import psycopg

    from auto_ontology.infra.postgres import (
        FRONTEND_SCHEMA,
        get_postgres_connection_string,
    )

    with psycopg.connect(get_postgres_connection_string(), connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT id FROM {FRONTEND_SCHEMA}."user" WHERE lower(email) = lower(%s) LIMIT 1',
                (email.strip(),),
            )
            row = cur.fetchone()
            return row[0] if row else None


def make_asker(
    platform: str,
    platform_user_id: str,
    display: str,
    email_lookup: Callable[[], str | None],
) -> Asker:
    """Resolve a sender to an account by email; never raises."""
    email = None
    try:
        email = email_lookup()
    except Exception:  # noqa: BLE001 - an unknown sender just gets no account
        logger.warning("Could not read the %s sender's email", platform, exc_info=True)
    user_id = None
    try:
        user_id = find_user_by_email(email)
    except Exception:  # noqa: BLE001 - same: fall back to the strictest access
        logger.warning(
            "Could not match %s sender to an account", platform, exc_info=True
        )
    return Asker(
        platform, platform_user_id, user_id, display or email or platform_user_id
    )


def parse_sse(lines: Iterable[str]) -> dict[str, Any] | None:
    """The final ``result`` or ``error`` event of a chat SSE stream."""
    final = None
    for line in lines:
        line = line.strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        try:
            event = json.loads(line[6:])
        except ValueError:
            continue
        if event.get("type") in ("result", "error"):
            final = event
    return final


def ask(
    question: str, asker: Asker, client: httpx.Client | None = None
) -> dict[str, Any]:
    """Run *question* through the chat API as *asker*; returns the final event."""
    headers = {
        "Content-Type": "application/json",
        "x-auto-ontology-user-id": asker.identity,
        "x-auto-ontology-source": asker.platform,
    }
    own = client is None
    client = client or httpx.Client(timeout=ASK_TIMEOUT_S)
    try:
        with client.stream(
            "POST",
            f"{BACKEND_URL}/api/chat/completions",
            json={"question": question},
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                detail = response.read().decode(errors="replace")[:300]
                return {
                    "type": "error",
                    "message": _http_error(response.status_code, detail),
                }
            final = parse_sse(response.iter_lines())
    except httpx.HTTPError as exc:
        logger.warning("Chat API call failed: %s", exc)
        return {"type": "error", "message": "问数服务暂时无法访问，请稍后再试。"}
    finally:
        if own:
            client.close()
    return final or {"type": "error", "message": "没有收到回答，请稍后再试。"}


def _http_error(status: int, detail: str) -> str:
    if status == 409 and "semantic" in detail.lower():
        return (
            "语义层还没有生成，暂时无法回答。请管理员先在“设置 → 语义编译”中开启编译。"
        )
    return f"问数服务返回错误（{status}），请稍后再试。"


def _rows(answer: dict[str, Any]) -> list[dict[str, Any]]:
    raw = answer.get("sql_response_from_db")
    if not raw:
        return []
    try:
        rows = json.loads(raw[0]) if isinstance(raw, list) else json.loads(raw)
    except (ValueError, TypeError):
        return []
    return rows if isinstance(rows, list) else []


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:60]


def format_table(rows: list[dict[str, Any]]) -> str:
    """The first rows as a markdown table, with a count of any left out."""
    if not rows or not isinstance(rows[0], dict):
        return ""
    columns = list(rows[0].keys())
    lines = [
        "| " + " | ".join(_cell(c) for c in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows[:MAX_ROWS]:
        lines.append("| " + " | ".join(_cell(row.get(c)) for c in columns) + " |")
    if len(rows) > MAX_ROWS:
        lines.append(
            f"\n（共 {len(rows)} 行，仅显示前 {MAX_ROWS} 行，完整结果请在网页端查看）"
        )
    return "\n".join(lines)


def format_provenance(provenance: dict[str, Any] | None) -> str:
    """A one-line summary of what the answer was built on."""
    if not provenance:
        return ""
    groups = [
        ("tables", "张表"),
        ("sql_attributes", "个指标"),
        ("column_attributes", "个列属性"),
        ("terms", "个术语"),
    ]
    items = [i for key, _ in groups for i in provenance.get(key) or []]
    parts = [
        f"{len(provenance.get(k) or [])} {unit}"
        for k, unit in groups
        if provenance.get(k)
    ]
    if not parts:
        return ""
    certified = sum(1 for i in items if i.get("status") == "certified")
    tables = "、".join(t["name"] for t in provenance.get("tables") or [])
    return f"回答依据：{' · '.join(parts)}（已认证 {certified}/{len(items)}）；数据表：{tables}"


def format_answer(event: dict[str, Any]) -> tuple[str, str]:
    """``(title, markdown)`` for the chat message answering *event*."""
    if event.get("type") == "error":
        return (
            "查询失败",
            f"抱歉，这次没能完成查询：{event.get('message') or '未知错误'}",
        )
    answer = event.get("answer") or {}
    parts = [str(answer.get("response") or "").strip()[:MAX_TEXT]]
    table = format_table(_rows(answer))
    if table:
        parts.append(table)
    elif answer.get("sql_code") and answer.get("sql_response_from_db") is not None:
        parts.append("查询结果为空。")
    sql = (answer.get("sql_code") or "").strip()
    if sql:
        parts.append(f"```sql\n{sql}\n```")
    provenance = format_provenance(answer.get("provenance"))
    if provenance:
        parts.append(provenance)
    return "问数结果", "\n\n".join(p for p in parts if p)


def answer_question(question: str, asker: Asker, *, asker_fn=ask) -> tuple[str, str]:
    """The reply to one message: help for an empty one, else the formatted answer."""
    if not question or question in ("帮助", "help", "?", "？"):
        return "使用说明", HELP_TEXT
    logger.info(
        "%s question from %s (%s): %s",
        asker.platform,
        asker.display,
        asker.identity,
        question,
    )
    return format_answer(asker_fn(question, asker))
