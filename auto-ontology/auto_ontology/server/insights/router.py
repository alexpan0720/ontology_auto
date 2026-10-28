# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for the question-quality board."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from auto_ontology.dal import insights as dal
from auto_ontology.insights.board import build_board
from auto_ontology.server.identity import resolve_internal_user

router = APIRouter()


@router.get("/insights")
def get_board(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    """Totals for the last *days*, and the questions that went wrong, worst first."""
    board = build_board(dal.list_outcomes(days), dal.dismissals())
    return {**board, "days": days}


class Dismiss(BaseModel):
    key: str


@router.post("/insights/dismiss")
def dismiss(body: Dismiss, request: Request) -> dict[str, bool]:
    """Hide a question until it fails again."""
    if not body.key.strip():
        raise HTTPException(status_code=400, detail="缺少问题标识")
    dal.dismiss(body.key, resolve_internal_user(request, required=False))
    return {"ok": True}


@router.delete("/insights/dismiss/{key}")
def undismiss(key: str) -> dict[str, bool]:
    """Show a hidden question again."""
    return {"ok": dal.undismiss(key)}
