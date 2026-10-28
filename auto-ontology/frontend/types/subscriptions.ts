// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/server/subscriptions/router.py`. */

export type PushPlatform = 'dingtalk' | 'feishu';

export type PushChannel = {
	id: string;
	name: string;
	platform: PushPlatform;
	/** Start and end of the webhook, enough to recognise it. */
	webhook_hint: string;
	has_secret: boolean;
	created: string | null;
};

export type ScheduleKind = 'hourly' | 'daily' | 'workdays' | 'weekly';
export type PushMode = 'always' | 'on_alert';
export type AlertType = 'none' | 'threshold' | 'change';
export type RunStatus = 'sent' | 'quiet' | 'failed';

export type SubscriptionFields = {
	name: string;
	sql: string;
	database_name: string | null;
	verified_query_id: string | null;
	schedule: ScheduleKind;
	time_of_day: string;
	weekday: number | null;
	timezone: string;
	channel_ids: string[];
	run_as_user_id: string | null;
	push_mode: PushMode;
	alert_type: AlertType;
	alert_column: string | null;
	alert_op: string | null;
	alert_value: number | null;
	enabled: boolean;
};

export type SubscriptionRun = {
	id: string;
	subscription_id: string;
	created: string | null;
	trigger: 'manual' | 'schedule';
	status: RunStatus;
	alerted: boolean;
	summary: string | null;
	rows?: Record<string, unknown>[] | null;
	deliveries: { channel_id: string; name: string; ok: boolean; detail: string }[];
};

export type Subscription = SubscriptionFields & {
	id: string;
	next_run_at: string | null;
	created: string | null;
	schedule_text: string;
	alert_text: string;
	last_run: SubscriptionRun | null;
};

export type SubscriptionOptions = {
	channels: PushChannel[];
	verified_queries: { id: string; question: string; sql: string; database_name: string | null }[];
	databases: string[];
	users: { id: string; name: string | null; email: string | null }[];
};

export type SubscriptionPreview = {
	columns: string[];
	rows: Record<string, unknown>[];
	row_count: number;
	alert: {
		triggered: boolean;
		lines: string[];
		note: string | null;
		value_column: string | null;
	};
	message: { title: string; body: string };
};
