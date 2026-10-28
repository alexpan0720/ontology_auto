# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add mask access policies

Revision ID: b5d2f0c8e1a4
Revises: a7c1e2d9f4b3
Create Date: 2026-10-28 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b5d2f0c8e1a4"
down_revision: Union[str, Sequence[str], None] = "a7c1e2d9f4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("access_policy", sa.Column("mask_style", sa.Text(), nullable=True))
    op.drop_constraint(
        op.f("ck_access_policy_kind_value"), "access_policy", type_="check"
    )
    op.drop_constraint(
        op.f("ck_access_policy_kind_target"), "access_policy", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_access_policy_kind_value"),
        "access_policy",
        "kind IN ('column', 'row', 'mask')",
    )
    op.create_check_constraint(
        op.f("ck_access_policy_kind_target"),
        "access_policy",
        "(kind IN ('column', 'mask') AND column_name IS NOT NULL)"
        " OR (kind = 'row' AND predicate IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM access_policy WHERE kind = 'mask'")
    op.drop_constraint(
        op.f("ck_access_policy_kind_target"), "access_policy", type_="check"
    )
    op.drop_constraint(
        op.f("ck_access_policy_kind_value"), "access_policy", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_access_policy_kind_value"),
        "access_policy",
        "kind IN ('column', 'row')",
    )
    op.create_check_constraint(
        op.f("ck_access_policy_kind_target"),
        "access_policy",
        "(kind = 'column' AND column_name IS NOT NULL)"
        " OR (kind = 'row' AND predicate IS NOT NULL)",
    )
    op.drop_column("access_policy", "mask_style")
