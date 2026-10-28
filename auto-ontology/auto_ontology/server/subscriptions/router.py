# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for push channels and metric subscriptions (with alert rules)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auto_ontology.dal import groups as groups_dal
from auto_ontology.dal import schema as s
from auto_ontology.dal import subscriptions as dal
from auto_ontology.dal.governance import list_verified
from auto_ontology.server.identity import resolve_internal_user
from auto_ontology.subscriptions import alerts, push, schedule, service

router = APIRouter()

Platform = Literal["dingtalk", "feishu"]


def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


@router.get("/push-channels")
def list_channels() -> dict[str, Any]:
    """Every channel, without its webhook token or secret."""
    rows = dal.list_channels()
    return {"data": rows, "count": len(rows)}


class ChannelCreate(BaseModel):
    name: str
    platform: Platform
    webhook_url: str
    secret: str | None = None


def _checked_channel(platform: str, name: str, url: str) -> None:
    if not name.strip():
        raise _bad("请填写渠道名称")
    try:
        push.validate(platform, url.strip())
    except push.ChannelError as exc:
        raise _bad(str(exc)) from exc


@router.post("/push-channels", status_code=201)
def create_channel(body: ChannelCreate, request: Request) -> dict[str, str]:
    """Add a group robot's webhook."""
    _checked_channel(body.platform, body.name, body.webhook_url)
    channel_id = dal.create_channel(
        name=body.name.strip(),
        platform=body.platform,
        webhook_url=body.webhook_url.strip(),
        secret=(body.secret or "").strip() or None,
        created_by=resolve_internal_user(request, required=False),
    )
    return {"id": channel_id}


class ChannelUpdate(BaseModel):
    name: str | None = None
    webhook_url: str | None = None
    #: Blank keeps the stored secret.
    secret: str | None = None
    clear_secret: bool = False


@router.patch("/push-channels/{channel_id}")
def update_channel(channel_id: str, body: ChannelUpdate) -> dict[str, bool]:
    """Rename a channel or replace its webhook / secret."""
    current = dal.get_channels([channel_id])
    if not current:
        raise HTTPException(status_code=404, detail="渠道不存在")
    _checked_channel(
        current[0]["platform"],
        body.name if body.name is not None else current[0]["name"],
        body.webhook_url.strip() if body.webhook_url else current[0]["webhook_url"],
    )
    changes = body.model_dump(exclude_none=True)
    if "webhook_url" in changes:
        changes["webhook_url"] = changes["webhook_url"].strip()
    dal.update_channel(channel_id, changes)
    return {"ok": True}


@router.delete("/push-channels/{channel_id}")
def delete_channel(channel_id: str) -> dict[str, bool]:
    """Delete a channel; subscriptions stop sending to it."""
    if not dal.delete_channel(channel_id):
        raise HTTPException(status_code=404, detail="渠道不存在")
    return {"ok": True}


class ChannelTest(BaseModel):
    #: A saved channel, or the unsaved fields below.
    channel_id: str | None = None
    platform: Platform | None = None
    webhook_url: str | None = None
    secret: str | None = None


@router.post("/push-channels/test")
def test_channel(body: ChannelTest) -> dict[str, Any]:
    """Send a test message, to a saved channel or to unsaved settings."""
    if body.channel_id:
        found = dal.get_channels([body.channel_id])
        if not found:
            raise HTTPException(status_code=404, detail="渠道不存在")
        channel = dict(found[0])
        if body.secret:
            channel["secret"] = body.secret
    else:
        if not body.platform or not body.webhook_url:
            raise _bad("请先填写平台和 Webhook 地址")
        channel = {
            "platform": body.platform,
            "webhook_url": body.webhook_url.strip(),
            "secret": (body.secret or "").strip() or None,
        }
    delivery = push.send(
        channel,
        "alexpan 本体 测试消息",
        "推送渠道配置成功，之后的指标订阅和预警会发到这个群。",
    )
    return {"ok": delivery.ok, "message": delivery.detail}


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


class SubscriptionFields(BaseModel):
    name: str
    sql: str
    database_name: str | None = None
    verified_query_id: str | None = None
    schedule: Literal["hourly", "daily", "workdays", "weekly"] = "daily"
    time_of_day: str = "09:00"
    weekday: int | None = None
    timezone: str = "Asia/Shanghai"
    channel_ids: list[str] = []
    run_as_user_id: str | None = None
    push_mode: Literal["always", "on_alert"] = "always"
    alert_type: Literal["none", "threshold", "change"] = "none"
    alert_column: str | None = None
    alert_op: str | None = None
    alert_value: float | None = None
    enabled: bool = True


def _validated(body: SubscriptionFields) -> dict[str, Any]:
    values = body.model_dump()
    values["name"] = values["name"].strip()
    values["sql"] = values["sql"].strip().rstrip(";").strip()
    values["alert_column"] = (values["alert_column"] or "").strip() or None
    if not values["name"]:
        raise _bad("请填写订阅名称")
    if not values["sql"]:
        raise _bad("请填写或选择查询 SQL")
    try:
        schedule.validate(
            values["schedule"],
            values["time_of_day"],
            values["weekday"],
            values["timezone"],
        )
        alerts.validate(values["alert_type"], values["alert_op"], values["alert_value"])
    except (schedule.ScheduleError, alerts.AlertRuleError) as exc:
        raise _bad(str(exc)) from exc
    if values["schedule"] != s.SCHEDULE_WEEKLY:
        values["weekday"] = None
    if values["alert_type"] == s.ALERT_NONE:
        values.update(alert_op=None, alert_value=None, push_mode=s.PUSH_ALWAYS)
    known = {c["id"] for c in dal.get_channels(values["channel_ids"])}
    if set(values["channel_ids"]) - known:
        raise _bad("所选推送渠道不存在")
    if values["enabled"] and not values["channel_ids"]:
        raise _bad("请至少选择一个推送渠道")
    values["next_run_at"] = (
        schedule.next_run(
            values["schedule"],
            values["time_of_day"],
            values["weekday"],
            values["timezone"],
            datetime.now(timezone.utc),
        )
        if values["enabled"]
        else None
    )
    return values


@router.get("/subscriptions")
def list_subscriptions() -> dict[str, Any]:
    """Every subscription with its last run."""
    rows = dal.list_subscriptions()
    for row in rows:
        row["schedule_text"] = schedule.describe(
            row["schedule"], row["time_of_day"], row["weekday"]
        )
        row["alert_text"] = alerts.describe(
            row["alert_type"], row["alert_column"], row["alert_op"], row["alert_value"]
        )
    return {"data": rows, "count": len(rows)}


@router.get("/subscriptions/options")
def subscription_options() -> dict[str, Any]:
    """What the form picks from: channels, certified queries, databases, users."""
    from auto_ontology.connectors import get_connectors

    users = groups_dal.list_users_and_groups()["users"]
    return {
        "channels": dal.list_channels(),
        "verified_queries": [
            {
                "id": q["id"],
                "question": q["question"],
                "sql": q["sql"],
                "database_name": q["database_name"],
            }
            for q in list_verified(status=s.VERIFIED_CERTIFIED)
        ],
        "databases": sorted(
            {
                c.database_name
                for c in get_connectors()
                if getattr(c, "database_name", None)
            }
        ),
        "users": [
            {"id": u["id"], "name": u.get("name"), "email": u.get("email")}
            for u in users
        ],
    }


@router.post("/subscriptions", status_code=201)
def create_subscription(body: SubscriptionFields, request: Request) -> dict[str, str]:
    """Create a subscription; it runs from its next scheduled time."""
    values = _validated(body)
    values["created_by"] = resolve_internal_user(request, required=False)
    return {"id": dal.create_subscription(values)}


@router.put("/subscriptions/{subscription_id}")
def update_subscription(
    subscription_id: str, body: SubscriptionFields
) -> dict[str, bool]:
    """Replace a subscription's settings; its next run is recomputed."""
    if dal.get_subscription(subscription_id) is None:
        raise HTTPException(status_code=404, detail="订阅不存在")
    dal.update_subscription(subscription_id, _validated(body))
    return {"ok": True}


class Toggle(BaseModel):
    enabled: bool


@router.post("/subscriptions/{subscription_id}/enabled")
def toggle_subscription(subscription_id: str, body: Toggle) -> dict[str, bool]:
    """Pause or resume a subscription."""
    current = dal.get_subscription(subscription_id)
    if current is None:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if body.enabled and not current["channel_ids"]:
        raise _bad("请先为订阅选择推送渠道")
    next_run_at = (
        schedule.next_run(
            current["schedule"],
            current["time_of_day"],
            current["weekday"],
            current["timezone"],
            datetime.now(timezone.utc),
        )
        if body.enabled
        else None
    )
    dal.update_subscription(
        subscription_id, {"enabled": body.enabled, "next_run_at": next_run_at}
    )
    return {"ok": True}


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(subscription_id: str) -> dict[str, bool]:
    """Delete a subscription and its run history."""
    if not dal.delete_subscription(subscription_id):
        raise HTTPException(status_code=404, detail="订阅不存在")
    return {"ok": True}


class RunRequest(BaseModel):
    trigger: Literal["manual", "schedule"] = "manual"


@router.post("/subscriptions/{subscription_id}/run")
def run_subscription(subscription_id: str, body: RunRequest) -> dict[str, Any]:
    """Run now: query, check the rule, push, and record the run."""
    try:
        return service.execute(subscription_id, trigger=body.trigger)
    except service.RunError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/subscriptions/{subscription_id}/runs")
def list_runs(subscription_id: str) -> dict[str, Any]:
    """The latest runs, newest first."""
    rows = dal.list_runs(subscription_id)
    return {"data": rows, "count": len(rows)}


class PreviewRequest(SubscriptionFields):
    name: str = "预览"
    subscription_id: str | None = None


@router.post("/subscriptions/preview")
def preview_subscription(body: PreviewRequest) -> dict[str, Any]:
    """Run unsaved settings without pushing, to check the query and the rule."""
    fields = body.model_dump()
    try:
        alerts.validate(fields["alert_type"], fields["alert_op"], fields["alert_value"])
        return service.preview(fields, body.subscription_id)
    except alerts.AlertRuleError as exc:
        raise _bad(str(exc)) from exc
    except service.RunError as exc:
        raise _bad(str(exc)) from exc
