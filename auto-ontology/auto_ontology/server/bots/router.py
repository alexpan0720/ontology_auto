# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for the DingTalk / Feishu bot settings."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auto_ontology.bots import config

router = APIRouter()

Platform = Literal["dingtalk", "feishu"]


@router.get("/bots")
def list_bots() -> dict[str, Any]:
    """Each platform's settings (without its secret) and connection status."""
    rows = config.load_all()
    return {"data": [config.public(p, rows.get(p)) for p in config.PLATFORMS]}


class BotSettings(BaseModel):
    enabled: bool
    app_id: str | None = None
    #: Blank keeps the stored secret.
    app_secret: str | None = None


@router.put("/bots/{platform}")
def save_bot(platform: Platform, body: BotSettings) -> dict[str, Any]:
    """Save a platform's settings; the bot service applies them within seconds."""
    if body.enabled:
        stored = config.load(platform) or {}
        if not (body.app_id or "").strip():
            raise HTTPException(status_code=400, detail="请填写 AppKey / App ID")
        if not ((body.app_secret or "").strip() or stored.get("app_secret")):
            raise HTTPException(status_code=400, detail="请填写 AppSecret")
    config.save(
        platform, enabled=body.enabled, app_id=body.app_id, app_secret=body.app_secret
    )
    return config.public(platform, config.load(platform))


class BotTest(BaseModel):
    app_id: str
    #: Blank tests the stored secret.
    app_secret: str | None = None


@router.post("/bots/{platform}/test")
async def test_bot(platform: Platform, body: BotTest) -> dict[str, Any]:
    """Check the credentials against the platform without saving them."""
    secret = (body.app_secret or "").strip() or (config.load(platform) or {}).get(
        "app_secret"
    )
    if not body.app_id.strip() or not secret:
        raise HTTPException(
            status_code=400, detail="请先填写 AppKey / App ID 和 AppSecret"
        )
    problem = await asyncio.to_thread(
        config.verify, platform, body.app_id.strip(), secret
    )
    return {"ok": problem is None, "message": problem or "凭据有效，可以连接"}
