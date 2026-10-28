# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for importing glossary terms from uploaded documents."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auto_ontology.dal import glossary_import as dal
from auto_ontology.dal import schema as s
from auto_ontology.glossary_import.parsers import DocumentError
from auto_ontology.glossary_import import service
from auto_ontology.glossary_import.service import start_import
from auto_ontology.server.identity import resolve_internal_user

router = APIRouter()


@router.post("/glossary-imports", status_code=201)
async def upload_document(
    request: Request, file: UploadFile = File(...)
) -> dict[str, str]:
    """Upload a document; terms are extracted in the background for review."""
    data = await file.read()
    try:
        # Parsing a large PDF is CPU work; keep it off the event loop.
        batch_id = await asyncio.to_thread(
            start_import,
            file.filename or "document",
            data,
            resolve_internal_user(request, required=False),
        )
    except DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": batch_id}


@router.get("/glossary-imports")
def list_imports() -> dict[str, Any]:
    """Every import batch, newest first, with candidate counts."""
    rows = dal.list_batches()
    return {"data": rows, "count": len(rows)}


@router.get("/glossary-imports/{batch_id}")
def get_import(batch_id: str) -> dict[str, Any]:
    """One batch with its candidates and what each would collide with."""
    batch = dal.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="导入记录不存在")
    return batch


@router.delete("/glossary-imports/{batch_id}")
def delete_import(batch_id: str) -> dict[str, bool]:
    """Delete a batch and its candidates (the glossary is not touched)."""
    if not dal.delete_batch(batch_id):
        raise HTTPException(status_code=404, detail="导入记录不存在")
    return {"ok": True}


class CandidateUpdate(BaseModel):
    term: str | None = None
    definition: str | None = None
    synonyms: list[str] | None = None


@router.patch("/glossary-candidates/{candidate_id}")
def update_candidate(candidate_id: str, body: CandidateUpdate) -> dict[str, bool]:
    """Edit a candidate before it is applied."""
    try:
        found = dal.update_candidate(candidate_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="候选术语不存在")
    return {"ok": True}


class ApplyRequest(BaseModel):
    candidate_ids: list[str]
    overwrite_existing: bool = False
    update_terms: bool = False


@router.post("/glossary-imports/{batch_id}/apply")
def apply_candidates(
    batch_id: str, body: ApplyRequest, request: Request
) -> dict[str, int]:
    """Write the chosen candidates to the glossary."""
    try:
        return service.apply_import(
            batch_id,
            body.candidate_ids,
            overwrite_existing=body.overwrite_existing,
            update_terms=body.update_terms,
            modified_by=resolve_internal_user(request, required=False),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="导入记录不存在") from exc


class RejectRequest(BaseModel):
    candidate_ids: list[str]


@router.post("/glossary-imports/{batch_id}/reject")
def reject_candidates(batch_id: str, body: RejectRequest) -> dict[str, int]:
    """Mark candidates as rejected."""
    return {"rejected": dal.set_status(body.candidate_ids, s.CANDIDATE_REJECTED)}
