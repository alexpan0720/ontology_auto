# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add question outcomes for the quality board

Revision ID: e2b7c4d6a8f1
Revises: d4a8c6e2f0b1
Create Date: 2026-10-29 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2b7c4d6a8f1"
down_revision: Union[str, Sequence[str], None] = "d4a8c6e2f0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('question_outcome',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=True),
    sa.Column('source', sa.Text(), server_default=sa.text("'app'"), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('outcome', sa.Text(), nullable=False),
    sa.Column('sql', sa.Text(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('message_id', sa.Text(), nullable=True),
    sa.CheckConstraint("outcome IN ('answered', 'empty', 'no_sql', 'error', 'blocked')", name=op.f('ck_question_outcome_outcome_value')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_question_outcome'))
    )
    op.create_index('ix_question_outcome_created', 'question_outcome', ['created'], unique=False)
    op.create_table('insight_dismissal',
    sa.Column('question_key', sa.Text(), nullable=False),
    sa.Column('dismissed_by', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('question_key', name=op.f('pk_insight_dismissal'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('insight_dismissal')
    op.drop_index('ix_question_outcome_created', table_name='question_outcome')
    op.drop_table('question_outcome')

