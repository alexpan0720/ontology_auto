# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add access requests

Revision ID: f3c8d5e7b9a2
Revises: e2b7c4d6a8f1
Create Date: 2026-10-29 09:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3c8d5e7b9a2"
down_revision: Union[str, Sequence[str], None] = "e2b7c4d6a8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('access_request',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('policy_id', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('question', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('decided_by', sa.Text(), nullable=True),
    sa.Column('decided', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=True),
    sa.Column('granted_group_id', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name=op.f('ck_access_request_status_value')),
    sa.ForeignKeyConstraint(['policy_id'], ['access_policy.id'], name=op.f('fk_access_request_policy_id_access_policy'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_access_request'))
    )
    op.create_index('ix_access_request_user_id', 'access_request', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_access_request_user_id', table_name='access_request')
    op.drop_table('access_request')

