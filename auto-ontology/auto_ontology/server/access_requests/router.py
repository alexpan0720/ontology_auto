# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for access requests: users ask, admins approve or reject."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auto_ontology.dal import access_requests as dal
from auto_ontology.server.identity import resolve_internal_user

router = APIRouter()


def _fail(exc: dal.RequestError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/access-requests/mine")
def my_requests(request: Request) -> dict[str, Any]:
    """What the caller's policies keep from them, and their requests."""
    user_id = resolve_internal_user(request, required=True)
    assert user_id is not None
    return {
        "restrictions": dal.restrictions(user_id),
        "requests": dal.list_requests(user_id=user_id),
    }


class RequestCreate(BaseModel):
    policy_id: str
    reason: str | None = None
    question: str | None = None


@router.post("/access-requests", status_code=201)
def create_request(body: RequestCreate, request: Request) -> dict[str, Any]:
    """Ask for what one policy keeps from the caller."""
    user_id = resolve_internal_user(request, required=True)
    assert user_id is not None
    try:
        return dal.create_request(
            user_id=user_id,
            policy_id=body.policy_id,
            reason=body.reason,
            question=body.question,
        )
    except dal.RequestError as exc:
        raise _fail(exc) from exc


@router.get("/access-requests")
def list_requests(
    status: Literal["pending", "approved", "rejected"] | None = None,
) -> dict[str, Any]:
    """Every request, newest first, for the reviewers."""
    rows = dal.list_requests(status=status)
    return {"data": rows, "count": len(rows), "pending": dal.pending_count()}


class Approve(BaseModel):
    #: A group the requester joins; empty uses the policy's own grant group.
    group_id: str | None = None
    note: str | None = None


@router.post("/access-requests/{request_id}/approve")
def approve(request_id: str, body: Approve, request: Request) -> dict[str, Any]:
    """Grant the request by adding the requester to a group the policy lets through."""
    try:
        return dal.approve(
            request_id,
            decided_by=resolve_internal_user(request, required=False),
            group_id=body.group_id,
            note=body.note,
        )
    except dal.RequestError as exc:
        raise _fail(exc) from exc


class Reject(BaseModel):
    note: str | None = None


@router.post("/access-requests/{request_id}/reject")
def reject(request_id: str, body: Reject, request: Request) -> dict[str, bool]:
    """Turn the request down, with an optional note the requester sees."""
    try:
        dal.reject(
            request_id,
            decided_by=resolve_internal_user(request, required=False),
            note=body.note,
        )
    except dal.RequestError as exc:
        raise _fail(exc) from exc
    return {"ok": True}
