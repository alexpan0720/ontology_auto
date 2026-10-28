# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add chat bot configuration

Revision ID: d4a8c6e2f0b1
Revises: c9e7a1b3d5f2
Create Date: 2026-10-28 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4a8c6e2f0b1"
down_revision: Union[str, Sequence[str], None] = "c9e7a1b3d5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bot_config",
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("app_id", sa.Text(), nullable=True),
        sa.Column("app_secret", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("status_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "platform IN ('dingtalk', 'feishu')",
            name=op.f("ck_bot_config_platform_value"),
        ),
        sa.PrimaryKeyConstraint("platform", name=op.f("pk_bot_config")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("bot_config")
