# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from auto_ontology.dal import schema as s
from auto_ontology.dal.access_requests import _binding, _effect, _target

POLICY = {
    "enabled": True,
    "schema_name": "demo_shop",
    "table_name": "customers",
    "column_name": "phone",
    "predicate": None,
}


@pytest.mark.parametrize(
    "kind, groups, member_of, binds",
    [
        (s.ACCESS_POLICY_COLUMN, [], set(), True),
        (s.ACCESS_POLICY_COLUMN, ["g1"], {"g1"}, False),
        (s.ACCESS_POLICY_MASK, ["g1"], {"g2"}, True),
        # A row policy with no groups applies to everyone: nothing to request.
        (s.ACCESS_POLICY_ROW, [], set(), False),
        (s.ACCESS_POLICY_ROW, ["g1"], set(), True),
        (s.ACCESS_POLICY_ROW, ["g1"], {"g1"}, False),
    ],
)
def test_which_policies_a_user_can_request(
    kind: str, groups: list[str], member_of: set[str], binds: bool
) -> None:
    assert _binding({**POLICY, "kind": kind, "group_ids": groups}, member_of) is binds


def test_disabled_policies_bind_nobody() -> None:
    policy = {
        **POLICY,
        "kind": s.ACCESS_POLICY_COLUMN,
        "group_ids": [],
        "enabled": False,
    }
    assert _binding(policy, set()) is False


def test_target_and_effect_read_naturally() -> None:
    column = {**POLICY, "kind": s.ACCESS_POLICY_COLUMN}
    assert _target(column) == "demo_shop.customers.phone"
    assert _effect(column) == "不能查看该字段"
    row = {
        **POLICY,
        "kind": s.ACCESS_POLICY_ROW,
        "column_name": None,
        "predicate": "channel = 'App'",
    }
    assert _target(row) == "demo_shop.customers"
    assert _effect(row) == "看不到满足「channel = 'App'」的行"
