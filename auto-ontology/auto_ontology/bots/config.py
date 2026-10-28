# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Bot configuration and the connection status the bot service reports."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store

PLATFORMS = (s.BOT_DINGTALK, s.BOT_FEISHU)

STATUS_CONNECTED = "connected"
STATUS_ERROR = "error"
STATUS_STOPPED = "stopped"


def load(platform: str) -> dict[str, Any] | None:
    rows = store().query_read(
        select(s.bot_config).where(s.bot_config.c.platform == platform)
    )
    return rows[0] if rows else None


def load_all() -> dict[str, dict[str, Any]]:
    rows = store().query_read(select(s.bot_config))
    return {row["platform"]: row for row in rows}


def public(platform: str, row: dict[str, Any] | None) -> dict[str, Any]:
    """What the settings page sees: never the secret, only whether one is saved."""
    row = row or {}
    return {
        "platform": platform,
        "enabled": bool(row.get("enabled")),
        "app_id": row.get("app_id") or "",
        "has_secret": bool(row.get("app_secret")),
        "status": row.get("status"),
        "status_detail": row.get("status_detail"),
        "status_updated": row["status_updated"].isoformat()
        if row.get("status_updated")
        else None,
    }


def save(
    platform: str, *, enabled: bool, app_id: str | None, app_secret: str | None
) -> None:
    """Upsert *platform*; a blank *app_secret* keeps the stored one."""
    values: dict[str, Any] = {
        "platform": platform,
        "enabled": enabled,
        "app_id": (app_id or "").strip() or None,
        "updated": func.now(),
    }
    secret = (app_secret or "").strip()
    if secret:
        values["app_secret"] = secret
    statement = insert(s.bot_config).values(**values)
    store().query_write(
        statement.on_conflict_do_update(
            index_elements=[s.bot_config.c.platform],
            set_={k: statement.excluded[k] for k in values if k != "platform"},
        )
    )


def set_status(platform: str, status: str, detail: str | None = None) -> None:
    store().query_write(
        insert(s.bot_config)
        .values(
            platform=platform,
            status=status,
            status_detail=(detail or "")[:500] or None,
            status_updated=func.now(),
        )
        .on_conflict_do_update(
            index_elements=[s.bot_config.c.platform],
            set_={
                "status": status,
                "status_detail": (detail or "")[:500] or None,
                "status_updated": func.now(),
            },
        )
    )


def verify(platform: str, app_id: str, app_secret: str) -> str | None:
    """``None`` when the credentials are accepted, else why not (user-facing)."""
    try:
        if platform == s.BOT_DINGTALK:
            response = httpx.get(
                "https://oapi.dingtalk.com/gettoken",
                params={"appkey": app_id, "appsecret": app_secret},
                timeout=10,
            )
            data = response.json()
            if data.get("errcode") == 0:
                return None
            return f"钉钉拒绝了凭据：{data.get('errmsg') or data}"
        response = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = response.json()
        if data.get("code") == 0:
            return None
        return f"飞书拒绝了凭据：{data.get('msg') or data}"
    except httpx.HTTPError as exc:
        return f"无法连接到{'钉钉' if platform == s.BOT_DINGTALK else '飞书'}开放平台：{exc}"
    except ValueError:
        return "开放平台返回了无法识别的响应"
