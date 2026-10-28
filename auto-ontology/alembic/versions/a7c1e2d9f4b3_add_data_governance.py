# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add data governance: access policies, access audit, verified queries

Revision ID: a7c1e2d9f4b3
Revises: 99d4d343dd0b
Create Date: 2026-10-28 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a7c1e2d9f4b3"
down_revision: Union[str, Sequence[str], None] = "99d4d343dd0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Column:
    return sa.Column(
        "id",
        sa.Text(),
        server_default=sa.text("(gen_random_uuid())::text"),
        nullable=False,
    )


def _created() -> sa.Column:
    return sa.Column(
        "created",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _text_array(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.ARRAY(sa.Text()),
        server_default=sa.text("'{}'::text[]"),
        nullable=False,
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "access_policy",
        _id(),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("table_id", sa.Text(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=True),
        sa.Column("predicate", sa.Text(), nullable=True),
        _text_array("group_ids"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "kind IN ('column', 'row')", name=op.f("ck_access_policy_kind_value")
        ),
        sa.CheckConstraint(
            "(kind = 'column' AND column_name IS NOT NULL)"
            " OR (kind = 'row' AND predicate IS NOT NULL)",
            name=op.f("ck_access_policy_kind_target"),
        ),
        sa.ForeignKeyConstraint(
            ["table_id"],
            ["catalog_table.id"],
            name=op.f("fk_access_policy_table_id_catalog_table"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_policy")),
    )
    op.create_index(
        "ix_access_policy_table_id", "access_policy", ["table_id"], unique=False
    )

    op.create_table(
        "access_audit",
        _id(),
        _created(),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _text_array("policy_ids"),
        sa.Column(
            "statements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('allowed', 'filtered', 'blocked')",
            name=op.f("ck_access_audit_decision_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_audit")),
    )
    op.create_index(
        "ix_access_audit_created", "access_audit", ["created"], unique=False
    )
    op.create_index(
        "ix_access_audit_user_id", "access_audit", ["user_id"], unique=False
    )

    op.create_table(
        "verified_query",
        _id(),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("database_name", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "source", sa.Text(), server_default=sa.text("'manual'"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        _created(),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'certified', 'rejected')",
            name=op.f("ck_verified_query_status_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verified_query")),
    )
    op.create_index(
        "ix_verified_query_status", "verified_query", ["status"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_verified_query_status", table_name="verified_query")
    op.drop_table("verified_query")
    op.drop_index("ix_access_audit_user_id", table_name="access_audit")
    op.drop_index("ix_access_audit_created", table_name="access_audit")
    op.drop_table("access_audit")
    op.drop_index("ix_access_policy_table_id", table_name="access_policy")
    op.drop_table("access_policy")
