# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add object types, property overrides and link types

Revision ID: b6e3f1a9c2d4
Revises: a4d9e6f8c0b3
Create Date: 2026-11-05 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6e3f1a9c2d4"
down_revision: Union[str, Sequence[str], None] = "a4d9e6f8c0b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('object_type',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('table_id', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('pk_column', sa.Text(), nullable=False),
    sa.Column('title_column', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'candidate'"), nullable=False),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('modified', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('modified_by', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('candidate', 'active')", name=op.f('ck_object_type_status_value')),
    sa.ForeignKeyConstraint(['table_id'], ['catalog_table.id'], name=op.f('fk_object_type_table_id_catalog_table'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_object_type')),
    sa.UniqueConstraint('table_id', name=op.f('uq_object_type_table_id'))
    )
    op.create_table('object_property',
    sa.Column('object_type_id', sa.Text(), nullable=False),
    sa.Column('column_name', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=True),
    sa.Column('hidden', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], name=op.f('fk_object_property_object_type_id_object_type'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('object_type_id', 'column_name', name=op.f('pk_object_property'))
    )
    op.create_table('link_type',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('object_type_id', sa.Text(), nullable=False),
    sa.Column('target_object_type_id', sa.Text(), nullable=False),
    sa.Column('source_column', sa.Text(), nullable=False),
    sa.Column('target_column', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=False),
    sa.Column('reverse_display_name', sa.Text(), nullable=False),
    sa.Column('origin', sa.Text(), server_default=sa.text("'manual'"), nullable=False),
    sa.Column('status', sa.Text(), server_default=sa.text("'candidate'"), nullable=False),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('modified', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('modified_by', sa.Text(), nullable=True),
    sa.CheckConstraint("origin IN ('foreign_key', 'semantic_fk', 'manual')", name=op.f('ck_link_type_origin_value')),
    sa.CheckConstraint("status IN ('candidate', 'active')", name=op.f('ck_link_type_status_value')),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], name=op.f('fk_link_type_object_type_id_object_type'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_object_type_id'], ['object_type.id'], name=op.f('fk_link_type_target_object_type_id_object_type'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_link_type')),
    sa.UniqueConstraint('object_type_id', 'source_column', 'target_object_type_id', name='uq_link_type_source')
    )
    op.create_index('ix_link_type_target_object_type_id', 'link_type', ['target_object_type_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_link_type_target_object_type_id', table_name='link_type')
    op.drop_table('link_type')
    op.drop_table('object_property')
    op.drop_table('object_type')
