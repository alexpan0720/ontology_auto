# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any

import pytest

os.environ.setdefault("REASONING_API_KEY", "test-key")
os.environ.setdefault("REASONING_ENDPOINT", "https://example.test/v1")
os.environ.setdefault("REASONING_MODEL", "openai/test-model")

from auto_ontology.dal import provenance as provenance_dal  # noqa: E402
from auto_ontology.retrieval.text_to_sql import main  # noqa: E402


def test_no_provenance_without_executed_sql() -> None:
    assert main._answer_provenance({"sql_tables": ["t1"]}) is None
    assert main._answer_provenance({"sql_code": "SELECT 1", "sql_tables": []}) is None


def test_traces_from_resolved_sql_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_fetch(**kwargs: Any) -> dict:
        seen.update(kwargs)
        return {"tables": [{"id": "t1"}]}

    monkeypatch.setattr(provenance_dal, "fetch_answer_provenance", fake_fetch)

    result = main._answer_provenance(
        {
            "sql_code": "SELECT 1",
            "sql_tables": ["t1"],
            "sql_columns": ["c1", "c2"],
            "sql_attributes": [{"id": "m1"}, {"name": "no id"}, "junk"],
            "retrieved_subject_term": {"id": "term1"},
        }
    )

    assert result == {"tables": [{"id": "t1"}]}
    assert seen == {
        "table_ids": ["t1"],
        "column_ids": ["c1", "c2"],
        "sql_attribute_ids": ["m1"],
        "extra_term_ids": ["term1"],
    }


def test_lookup_failure_does_not_fail_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(**_kwargs: Any) -> dict:
        raise RuntimeError("database down")

    monkeypatch.setattr(provenance_dal, "fetch_answer_provenance", broken)

    assert (
        main._answer_provenance({"sql_code": "SELECT 1", "sql_tables": ["t1"]}) is None
    )
