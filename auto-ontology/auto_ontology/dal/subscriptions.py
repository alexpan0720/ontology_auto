# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Push channels, metric subscriptions and their runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy import delete, func, insert, select, update

from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store, write_transaction

#: Result rows kept per run, for the next change comparison and the history.
MAX_STORED_ROWS = 200


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


def _channel_public(row: dict[str, Any]) -> dict[str, Any]:
    url = row["webhook_url"]
    return {
        "id": row["id"],
        "name": row["name"],
        "platform": row["platform"],
        # Enough to recognise the robot, not enough to post as it.
        "webhook_hint": url[:48] + "…" + url[-4:] if len(url) > 56 else url,
        "has_secret": bool(row["secret"]),
        "created": _iso(row["created"]),
    }


def list_channels() -> list[dict[str, Any]]:
    rows = store().query_read(select(s.push_channel).order_by(s.push_channel.c.created))
    return [_channel_public(r) for r in rows]


def get_channels(channel_ids: list[str]) -> list[dict[str, Any]]:
    """Channels with their webhook and secret, for sending."""
    if not channel_ids:
        return []
    return store().query_read(
        select(s.push_channel).where(s.push_channel.c.id.in_(channel_ids))
    )


def create_channel(
    *,
    name: str,
    platform: str,
    webhook_url: str,
    secret: str | None,
    created_by: str | None,
) -> str:
    rows = store().query_write(
        insert(s.push_channel)
        .values(
            name=name,
            platform=platform,
            webhook_url=webhook_url,
            secret=secret or None,
            created_by=created_by,
        )
        .returning(s.push_channel.c.id)
    )
    return rows[0]["id"]


def update_channel(channel_id: str, changes: dict[str, Any]) -> bool:
    values = {k: v for k, v in changes.items() if k in ("name", "webhook_url")}
    # A blank secret keeps the stored one; clearing it is explicit.
    if changes.get("secret"):
        values["secret"] = changes["secret"]
    if changes.get("clear_secret"):
        values["secret"] = None
    if not values:
        return bool(get_channels([channel_id]))
    rows = store().query_write(
        update(s.push_channel)
        .where(s.push_channel.c.id == channel_id)
        .values(**values)
        .returning(s.push_channel.c.id)
    )
    return bool(rows)


def delete_channel(channel_id: str) -> bool:
    with write_transaction():
        store().query_write(
            update(s.metric_subscription)
            .where(s.metric_subscription.c.channel_ids.any(channel_id))
            .values(
                channel_ids=func.array_remove(
                    s.metric_subscription.c.channel_ids, channel_id
                )
            )
        )
        rows = store().query_write(
            delete(s.push_channel)
            .where(s.push_channel.c.id == channel_id)
            .returning(s.push_channel.c.id)
        )
    return bool(rows)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

EDITABLE = (
    "name",
    "sql",
    "database_name",
    "verified_query_id",
    "schedule",
    "time_of_day",
    "weekday",
    "timezone",
    "channel_ids",
    "run_as_user_id",
    "push_mode",
    "alert_type",
    "alert_column",
    "alert_op",
    "alert_value",
    "enabled",
    "next_run_at",
)


def _subscription_public(
    row: dict[str, Any], last: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        **row,
        "channel_ids": list(row["channel_ids"] or []),
        "next_run_at": _iso(row["next_run_at"]),
        "created": _iso(row["created"]),
        "last_run": _run_public(last, with_rows=False) if last else None,
    }


def _latest_runs() -> dict[str, dict[str, Any]]:
    latest = (
        select(
            s.subscription_run.c.subscription_id,
            func.max(s.subscription_run.c.created).label("created"),
        )
        .group_by(s.subscription_run.c.subscription_id)
        .subquery()
    )
    rows = store().query_read(
        select(s.subscription_run).join(
            latest,
            (latest.c.subscription_id == s.subscription_run.c.subscription_id)
            & (latest.c.created == s.subscription_run.c.created),
        )
    )
    return {r["subscription_id"]: r for r in rows}


def list_subscriptions() -> list[dict[str, Any]]:
    last = _latest_runs()
    rows = store().query_read(
        select(s.metric_subscription).order_by(s.metric_subscription.c.created)
    )
    return [_subscription_public(r, last.get(r["id"])) for r in rows]


def get_subscription(subscription_id: str) -> dict[str, Any] | None:
    rows = store().query_read(
        select(s.metric_subscription).where(
            s.metric_subscription.c.id == subscription_id
        )
    )
    return rows[0] if rows else None


def create_subscription(values: dict[str, Any]) -> str:
    rows = store().query_write(
        insert(s.metric_subscription)
        .values(**{k: v for k, v in values.items() if k in EDITABLE + ("created_by",)})
        .returning(s.metric_subscription.c.id)
    )
    return rows[0]["id"]


def update_subscription(subscription_id: str, values: dict[str, Any]) -> bool:
    rows = store().query_write(
        update(s.metric_subscription)
        .where(s.metric_subscription.c.id == subscription_id)
        .values(**{k: v for k, v in values.items() if k in EDITABLE})
        .returning(s.metric_subscription.c.id)
    )
    return bool(rows)


def delete_subscription(subscription_id: str) -> bool:
    rows = store().query_write(
        delete(s.metric_subscription)
        .where(s.metric_subscription.c.id == subscription_id)
        .returning(s.metric_subscription.c.id)
    )
    return bool(rows)


def claim_due(
    now: datetime, next_after: Callable[[dict[str, Any]], datetime | None]
) -> list[str]:
    """Ids of enabled subscriptions due at *now*, each moved to its next slot.

    Locked rows are skipped, so concurrent schedulers split the work instead
    of running anything twice.
    """
    claimed = []
    with write_transaction():
        rows = store().query_read(
            select(s.metric_subscription)
            .where(
                s.metric_subscription.c.enabled.is_(True),
                s.metric_subscription.c.next_run_at <= now,
            )
            .with_for_update(skip_locked=True)
        )
        for row in rows:
            store().query_write(
                update(s.metric_subscription)
                .where(s.metric_subscription.c.id == row["id"])
                .values(next_run_at=next_after(row))
            )
            claimed.append(row["id"])
    return claimed


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def _run_public(row: dict[str, Any], *, with_rows: bool = True) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if with_rows or k != "rows"}
    out["created"] = _iso(row["created"])
    return out


def record_run(
    *,
    subscription_id: str,
    trigger: str,
    status: str,
    alerted: bool,
    summary: str | None,
    rows: list[dict[str, Any]] | None,
    deliveries: list[dict[str, Any]],
) -> dict[str, Any]:
    created = store().query_write(
        insert(s.subscription_run)
        .values(
            subscription_id=subscription_id,
            trigger=trigger,
            status=status,
            alerted=alerted,
            summary=summary,
            rows=rows[:MAX_STORED_ROWS] if rows is not None else None,
            deliveries=deliveries,
        )
        .returning(*s.subscription_run.c)
    )
    return _run_public(created[0])


def list_runs(subscription_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = store().query_read(
        select(s.subscription_run)
        .where(s.subscription_run.c.subscription_id == subscription_id)
        .order_by(s.subscription_run.c.created.desc())
        .limit(limit)
    )
    return [_run_public(r) for r in rows]


def previous_rows(subscription_id: str) -> list[dict[str, Any]] | None:
    """The rows of the last successful run, the baseline of a change alert."""
    rows = store().query_read(
        select(s.subscription_run.c.rows)
        .where(
            s.subscription_run.c.subscription_id == subscription_id,
            s.subscription_run.c.status != s.RUN_FAILED,
            s.subscription_run.c.rows.is_not(None),
        )
        .order_by(s.subscription_run.c.created.desc())
        .limit(1)
    )
    return rows[0]["rows"] if rows else None
