# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from auto_ontology.dal.governance import is_key_column


@pytest.mark.parametrize(
    "name, expected",
    [
        ("id", True),
        ("ID", True),
        ("customer_id", True),
        ("orderId", True),
        ("customer_name", False),
        ("phone", False),
        ("paid", False),
        ("valid", False),
    ],
)
def test_identifier_columns_are_recognised(name: str, expected: bool) -> None:
    """One-click masking skips join keys; ``paid`` / ``valid`` are not keys."""
    assert is_key_column(name) is expected
