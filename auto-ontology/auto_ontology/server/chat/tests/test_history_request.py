# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from auto_ontology.server.chat.helpers import ChatRequest


def test_history_is_optional_and_typed() -> None:
    assert ChatRequest(question="q").history is None
    request = ChatRequest(
        question="那华东呢？",
        history=[{"question": "各品类销售额", "response": "…", "sql_code": "SELECT 1"}],
    )
    assert request.history is not None
    assert request.history[0].model_dump() == {
        "question": "各品类销售额",
        "response": "…",
        "sql_code": "SELECT 1",
    }
