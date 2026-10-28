# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Requests for a field or rows an access policy keeps from a user.

A user sees which policies bind them (:func:`restrictions`) and asks for one;
an admin approves by adding them to a group the policy lets through. With no
group picked, approval uses the policy's own "授权" group, created on first
use, so granting one person never loosens the policy for anyone else.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from auto_ontology.dal import governance
from auto_ontology.dal import groups as groups_dal
from auto_ontology.dal import schema as s
from auto_ontology.dal.session import store, write_transaction

#: Colour of the groups approval creates, the product's brand blue.
GRANT_GROUP_COLOR = "#2563eb"


class RequestError(ValueError):
    """A request that cannot be made or decided; the message is user-facing."""


def _target(policy: dict[str, Any]) -> str:
    table = f"{policy['schema_name']}.{policy['table_name']}"
    return f"{table}.{policy['column_name']}" if policy["column_name"] else table


def _effect(policy: dict[str, Any]) -> str:
    if policy["kind"] == s.ACCESS_POLICY_COLUMN:
        return "不能查看该字段"
    if policy["kind"] == s.ACCESS_POLICY_MASK:
        return "只能看到遮掩后的值"
    return f"看不到满足「{policy['predicate']}」的行"


def _is_admin(user_id: str, member_of: list[dict[str, Any]]) -> bool:
    from auto_ontology.server.users.postgres_dal import get_user_role

    return get_user_role(user_id) == s.GROUP_ROLE_ADMIN or any(
        g["role"] == s.GROUP_ROLE_ADMIN for g in member_of
    )


def _binding(policy: dict[str, Any], member_of: set[str]) -> bool:
    """Whether *policy* keeps something from a user in groups *member_of*."""
    if not policy["enabled"]:
        return False
    groups = set(policy["group_ids"] or [])
    if policy["kind"] == s.ACCESS_POLICY_ROW:
        # A row policy with no groups is everyone's; one naming groups shows
        # its rows only to them.
        return bool(groups) and not groups & member_of
    return not groups & member_of


def restrictions(user_id: str) -> list[dict[str, Any]]:
    """Every policy that keeps something from *user_id*, with any open request."""
    groups = governance._user_groups(user_id)
    if _is_admin(user_id, groups):
        return []
    member_of = {g["id"] for g in groups}
    pending = {
        r["policy_id"]: r["id"]
        for r in store().query_read(
            select(s.access_request.c.id, s.access_request.c.policy_id).where(
                s.access_request.c.user_id == user_id,
                s.access_request.c.status == s.REQUEST_PENDING,
            )
        )
    }
    return [
        {
            "policy_id": p["id"],
            "kind": p["kind"],
            "database_name": p["database_name"],
            "target": _target(p),
            "column_name": p["column_name"],
            "effect": _effect(p),
            "description": p["description"],
            "pending_request_id": pending.get(p["id"]),
        }
        for p in governance.list_policies()
        if _binding(p, member_of)
    ]


def create_request(
    *, user_id: str, policy_id: str, reason: str | None, question: str | None
) -> dict[str, Any]:
    """Ask for what *policy_id* keeps from *user_id*; an open request is reused."""
    binding = {r["policy_id"]: r for r in restrictions(user_id)}
    entry = binding.get(policy_id)
    if entry is None:
        raise RequestError("你已经可以访问这项数据，或该策略已不存在")
    if entry["pending_request_id"]:
        return {"id": entry["pending_request_id"], "created": False}
    rows = store().query_write(
        pg_insert(s.access_request)
        .values(
            user_id=user_id,
            policy_id=policy_id,
            reason=(reason or "").strip()[:1000] or None,
            question=(question or "").strip()[:1000] or None,
        )
        .returning(s.access_request.c.id)
    )
    return {"id": rows[0]["id"], "created": True}


def list_requests(
    *, user_id: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    conditions = []
    if user_id:
        conditions.append(s.access_request.c.user_id == user_id)
    if status:
        conditions.append(s.access_request.c.status == status)
    rows = store().query_read(
        select(s.access_request)
        .where(*conditions)
        .order_by(s.access_request.c.created.desc())
        .limit(500)
    )
    policies = {p["id"]: p for p in governance.list_policies()}
    accounts = groups_dal._accounts_by_id(
        sorted(
            {r["user_id"] for r in rows}
            | {r["decided_by"] for r in rows if r["decided_by"]}
        )
    )
    group_names = governance._group_names()
    out = []
    for row in rows:
        policy = policies.get(row["policy_id"])
        requester = accounts.get(row["user_id"]) or {}
        decider = accounts.get(row["decided_by"] or "") or {}
        out.append(
            {
                **row,
                "created": row["created"].isoformat() if row["created"] else None,
                "decided": row["decided"].isoformat() if row["decided"] else None,
                "user_name": requester.get("name") or row["user_id"],
                "user_email": requester.get("email"),
                "decided_by_name": decider.get("name") or row["decided_by"],
                "kind": policy["kind"] if policy else None,
                "target": _target(policy) if policy else None,
                "effect": _effect(policy) if policy else None,
                "policy_group_ids": list(policy["group_ids"] or []) if policy else [],
                "granted_group_name": group_names.get(row["granted_group_id"] or ""),
            }
        )
    return out


def _pending(request_id: str) -> dict[str, Any]:
    rows = store().query_read(
        select(s.access_request).where(s.access_request.c.id == request_id)
    )
    if not rows:
        raise RequestError("申请不存在")
    if rows[0]["status"] != s.REQUEST_PENDING:
        raise RequestError("该申请已处理")
    return rows[0]


def _grant_group(policy: dict[str, Any]) -> str:
    """The policy's own grant group, created on first use."""
    name = f"授权·{_target(policy)}"[:80]
    for group in groups_dal.list_groups():
        if group["name"].strip().lower() == name.lower():
            return group["id"]
    group = groups_dal.create_group(
        name=name,
        description=f"由权限申请审批自动创建，成员可访问 {_target(policy)}",
        color=GRANT_GROUP_COLOR,
        role=s.GROUP_ROLE_VIEWER,
        user_ids=[],
    )
    return group["id"]


def approve(
    request_id: str, *, decided_by: str | None, group_id: str | None, note: str | None
) -> dict[str, Any]:
    """Add the requester to *group_id* (or the policy's grant group) and let it through."""
    request = _pending(request_id)
    policy = next(
        (p for p in governance.list_policies() if p["id"] == request["policy_id"]), None
    )
    if policy is None:
        raise RequestError("对应的权限策略已被删除")
    if group_id:
        if groups_dal.get_group(group_id) is None:
            raise RequestError("用户组不存在")
    else:
        group_id = _grant_group(policy)
    with write_transaction():
        if group_id not in (policy["group_ids"] or []):
            store().query_write(
                update(s.access_policy)
                .where(s.access_policy.c.id == policy["id"])
                .values(group_ids=[*(policy["group_ids"] or []), group_id])
            )
        store().query_write(
            pg_insert(s.user_group__member)
            .values(group_id=group_id, user_id=request["user_id"])
            .on_conflict_do_nothing()
        )
        store().query_write(
            update(s.access_request)
            .where(s.access_request.c.id == request_id)
            .values(
                status=s.REQUEST_APPROVED,
                decided_by=decided_by,
                decided=datetime.now(timezone.utc),
                decision_note=(note or "").strip()[:1000] or None,
                granted_group_id=group_id,
            )
        )
    return {"ok": True, "group_id": group_id}


def reject(request_id: str, *, decided_by: str | None, note: str | None) -> None:
    _pending(request_id)
    store().query_write(
        update(s.access_request)
        .where(s.access_request.c.id == request_id)
        .values(
            status=s.REQUEST_REJECTED,
            decided_by=decided_by,
            decided=datetime.now(timezone.utc),
            decision_note=(note or "").strip()[:1000] or None,
        )
    )


def pending_count() -> int:
    rows = store().query_read(
        select(s.access_request.c.id).where(
            s.access_request.c.status == s.REQUEST_PENDING
        )
    )
    return len(rows)
