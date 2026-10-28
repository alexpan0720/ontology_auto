# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Start a glossary import: parse now, extract in the background."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from auto_ontology.dal import glossary_import as dal
from auto_ontology.glossary_import.extractor import extract_terms
from auto_ontology.glossary_import.parsers import chunk, extract_sections

logger = logging.getLogger(__name__)

#: Upper bound on chunks extracted per document (about 240k characters). The
#: rest is skipped and the batch is marked truncated, so the page can say so.
MAX_CHUNKS = 40
MAX_BYTES = 20 * 1024 * 1024


def _default_llm() -> Any:
    from auto_ontology.utils.llm_invoke import (
        get_llm_client,
        get_non_reasoning_llm_client,
    )

    try:
        return get_non_reasoning_llm_client(max_tokens=4096)
    except Exception:  # noqa: BLE001 - fall back to the main model
        return get_llm_client(max_tokens=4096)


def run_batch(batch_id: str, chunks: list[str], llm: Any) -> None:
    """Extract and store candidates for one batch; never raises."""
    try:
        candidates = extract_terms(
            chunks, llm, on_chunk=lambda done: dal.set_progress(batch_id, done)
        )
        dal.finish_batch(batch_id, candidates)
        logger.info(
            "Glossary import %s: %d candidate(s) from %d chunk(s)",
            batch_id,
            len(candidates),
            len(chunks),
        )
    except Exception as exc:  # noqa: BLE001 - recorded on the batch for the page
        logger.exception("Glossary import %s failed", batch_id)
        dal.fail_batch(batch_id, f"提取失败：{exc}")


def start_import(
    file_name: str,
    data: bytes,
    created_by: str | None,
    *,
    llm_factory: Callable[[], Any] = _default_llm,
    background: bool = True,
) -> str:
    """Parse *data* (raising ``DocumentError`` on an unusable file) and start extraction."""
    from auto_ontology.glossary_import.parsers import DocumentError

    if len(data) > MAX_BYTES:
        raise DocumentError("文件超过 20 MB，请拆分后上传")
    chunks = chunk(extract_sections(file_name, data))
    truncated = len(chunks) > MAX_CHUNKS
    chunks = chunks[:MAX_CHUNKS]
    batch_id = dal.create_batch(
        file_name=file_name,
        chunks_total=len(chunks),
        truncated=truncated,
        created_by=created_by,
    )
    llm = llm_factory()
    if background:
        threading.Thread(
            target=run_batch,
            args=(batch_id, chunks, llm),
            daemon=True,
            name=f"glossary-import-{batch_id[:8]}",
        ).start()
    else:
        run_batch(batch_id, chunks, llm)
    return batch_id


def apply_import(
    batch_id: str,
    candidate_ids: list[str],
    *,
    overwrite_existing: bool,
    update_terms: bool,
    modified_by: str | None,
) -> dict[str, int]:
    """Apply the chosen candidates, then refresh the embeddings of updated terms."""
    from auto_ontology.server.terms import service as term_service

    result = dal.apply_candidates(
        batch_id,
        candidate_ids,
        overwrite_existing=overwrite_existing,
        update_terms=update_terms,
        modified_by=modified_by,
    )
    for term_id in result.pop("updated_term_ids"):
        try:
            term_service.refresh_term_embeddings(term_id, refresh_dependent_attrs=False)
        except Exception:  # noqa: BLE001 - the description is saved regardless
            logger.warning(
                "Failed to refresh embeddings for term %r", term_id, exc_info=True
            )
    return result
