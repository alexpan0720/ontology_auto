# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Ask the LLM for the terms each chunk defines, then merge them across chunks."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedTerm(BaseModel):
    term: str = Field(description="术语名称，使用文档中的写法")
    definition: str = Field(description="术语的定义或计算口径，忠于原文，可简洁改写")
    synonyms: list[str] = Field(
        default_factory=list, description="同义词、别名、英文名或缩写，没有则为空"
    )
    evidence: str = Field(
        default="", description="定义所依据的原文摘录，一句话，不超过 80 字"
    )


class ExtractionResult(BaseModel):
    terms: list[ExtractedTerm] = Field(default_factory=list)


SYSTEM_PROMPT = """你是企业数据治理专家，负责从业务文档中整理术语表。

从给定的文档片段中抽取业务术语及其定义，包括：业务指标（及其计算口径）、业务对象、维度、状态或枚举值的含义、数据字典中字段的业务含义、缩写和专有名词。

要求：
1. 只抽取片段中确实给出了含义或口径的术语；定义必须来自原文，可以简洁改写，但不能编造或补充原文没有的内容。
2. 跳过“数据”“系统”“用户”这类没有给出特定含义的通用词。
3. 数据字典表格中，字段的中文名作为术语，说明列作为定义；英文字段名放入同义词。
4. 同义词只放原文中明确出现的别名、英文名或缩写。
5. evidence 摘录定义所在的原文句子，不超过 80 字。
6. 片段中没有任何术语定义时，返回空列表。"""


def _key(term: str) -> str:
    """Merge key: case, spacing and trailing punctuation do not make a new term."""
    return re.sub(r"[\s　·•:：,，.。;；()（）\"'“”]+", "", term).casefold()


def merge_terms(batches: list[list[ExtractedTerm]]) -> list[dict[str, Any]]:
    """One entry per distinct term, in first-seen order.

    The first definition wins — documents tend to define a term where they
    introduce it — but a later one replaces it when the first is a mere
    fragment. Synonyms are unioned, without the term itself.
    """
    merged: dict[str, dict[str, Any]] = {}
    for batch in batches:
        for item in batch:
            term = " ".join(item.term.split())
            definition = " ".join(item.definition.split())
            if not term or not definition:
                continue
            key = _key(term)
            if not key:
                continue
            entry = merged.get(key)
            if entry is None:
                merged[key] = entry = {
                    "term": term,
                    "definition": definition,
                    "synonyms": [],
                    "evidence": item.evidence.strip()[:300] or None,
                }
            elif len(entry["definition"]) < 8 <= len(definition):
                entry["definition"] = definition
            for synonym in item.synonyms:
                synonym = " ".join(synonym.split())
                if (
                    synonym
                    and _key(synonym) != key
                    and _key(synonym) not in {_key(s) for s in entry["synonyms"]}
                ):
                    entry["synonyms"].append(synonym)
    return list(merged.values())


def extract_terms(
    chunks: list[str],
    llm: Any,
    *,
    on_chunk: Callable[[int], None] | None = None,
) -> list[dict[str, Any]]:
    """Run the extractor over every chunk and merge what it finds.

    A chunk the model fails on is skipped (and logged) rather than failing the
    whole document: one unreadable table should not cost the rest.
    """
    from auto_ontology.utils.llm_invoke import invoke_with_structured_output

    batches: list[list[ExtractedTerm]] = []
    for index, text in enumerate(chunks, 1):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"文档片段（{index}/{len(chunks)}）：\n\n{text}"),
        ]
        try:
            result = invoke_with_structured_output(llm, messages, ExtractionResult)
        except Exception:  # noqa: BLE001 - see docstring
            logger.exception("Glossary extraction failed on chunk %d", index)
            result = None
        if result is not None:
            batches.append(result.terms)
        if on_chunk is not None:
            on_chunk(index)
    return merge_terms(batches)
