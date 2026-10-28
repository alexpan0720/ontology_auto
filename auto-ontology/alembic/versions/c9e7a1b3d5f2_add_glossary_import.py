# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add glossary import from documents

Revision ID: c9e7a1b3d5f2
Revises: b5d2f0c8e1a4
Create Date: 2026-10-28 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9e7a1b3d5f2"
down_revision: Union[str, Sequence[str], None] = "b5d2f0c8e1a4"
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


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "glossary_import",
        _id(),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'processing'"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "chunks_total", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "chunks_done", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "status IN ('processing', 'done', 'failed')",
            name=op.f("ck_glossary_import_status_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_glossary_import")),
    )
    op.create_table(
        "glossary_candidate",
        _id(),
        sa.Column("import_id", sa.Text(), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "synonyms",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
        _created(),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name=op.f("ck_glossary_candidate_status_value"),
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["glossary_import.id"],
            name=op.f("fk_glossary_candidate_import_id_glossary_import"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_glossary_candidate")),
    )
    op.create_index(
        "ix_glossary_candidate_import_id",
        "glossary_candidate",
        ["import_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_glossary_candidate_import_id", table_name="glossary_candidate")
    op.drop_table("glossary_candidate")
    op.drop_table("glossary_import")
