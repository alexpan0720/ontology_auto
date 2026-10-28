# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""add metric subscriptions and push channels

Revision ID: a4d9e6f8c0b3
Revises: f3c8d5e7b9a2
Create Date: 2026-10-29 09:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a4d9e6f8c0b3"
down_revision: Union[str, Sequence[str], None] = "f3c8d5e7b9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('push_channel',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('platform', sa.Text(), nullable=False),
    sa.Column('webhook_url', sa.Text(), nullable=False),
    sa.Column('secret', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform IN ('dingtalk', 'feishu')", name=op.f('ck_push_channel_platform_value')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_push_channel'))
    )
    op.create_table('metric_subscription',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('sql', sa.Text(), nullable=False),
    sa.Column('database_name', sa.Text(), nullable=True),
    sa.Column('verified_query_id', sa.Text(), nullable=True),
    sa.Column('schedule', sa.Text(), nullable=False),
    sa.Column('time_of_day', sa.Text(), server_default=sa.text("'09:00'"), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=True),
    sa.Column('timezone', sa.Text(), server_default=sa.text("'Asia/Shanghai'"), nullable=False),
    sa.Column('channel_ids', sa.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('run_as_user_id', sa.Text(), nullable=True),
    sa.Column('push_mode', sa.Text(), server_default=sa.text("'always'"), nullable=False),
    sa.Column('alert_type', sa.Text(), server_default=sa.text("'none'"), nullable=False),
    sa.Column('alert_column', sa.Text(), nullable=True),
    sa.Column('alert_op', sa.Text(), nullable=True),
    sa.Column('alert_value', sa.Float(), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("alert_type IN ('none', 'threshold', 'change')", name=op.f('ck_metric_subscription_alert_type_value')),
    sa.CheckConstraint("push_mode IN ('always', 'on_alert')", name=op.f('ck_metric_subscription_push_mode_value')),
    sa.CheckConstraint("schedule IN ('hourly', 'daily', 'workdays', 'weekly')", name=op.f('ck_metric_subscription_schedule_value')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_metric_subscription'))
    )
    op.create_table('subscription_run',
    sa.Column('id', sa.Text(), server_default=sa.text('(gen_random_uuid())::text'), nullable=False),
    sa.Column('subscription_id', sa.Text(), nullable=False),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('trigger', sa.Text(), server_default=sa.text("'schedule'"), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('alerted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('rows', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('deliveries', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.CheckConstraint("status IN ('sent', 'quiet', 'failed')", name=op.f('ck_subscription_run_status_value')),
    sa.ForeignKeyConstraint(['subscription_id'], ['metric_subscription.id'], name=op.f('fk_subscription_run_subscription_id_metric_subscription'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subscription_run'))
    )
    op.create_index('ix_subscription_run_subscription_id', 'subscription_run', ['subscription_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_subscription_run_subscription_id', table_name='subscription_run')
    op.drop_table('subscription_run')
    op.drop_table('metric_subscription')
    op.drop_table('push_channel')

