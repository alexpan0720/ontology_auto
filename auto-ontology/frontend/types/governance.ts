// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/server/governance/router.py`. */

export type AccessPolicyKind = 'column' | 'row' | 'mask';

export type MaskStyle = 'phone' | 'email' | 'id_number' | 'name' | 'address' | 'partial' | 'full';

export type AccessPolicy = {
	id: string;
	kind: AccessPolicyKind;
	table_id: string;
	table_name: string;
	schema_name: string;
	database_name: string;
	column_name: string | null;
	predicate: string | null;
	/** Chosen by hand; null lets the backend pick one from the column name. */
	mask_style: MaskStyle | null;
	/** The style a mask policy actually applies. */
	effective_mask_style: MaskStyle | null;
	group_ids: string[];
	group_names: string[];
	description: string | null;
	enabled: boolean;
	created: string | null;
};

export type AccessPolicyInput = {
	kind: AccessPolicyKind;
	table_id: string;
	column_name?: string | null;
	predicate?: string | null;
	mask_style?: MaskStyle | null;
	group_ids: string[];
	description?: string | null;
	enabled?: boolean;
};

export type PolicyTableOption = {
	id: string;
	name: string;
	schema_name: string;
	database_name: string;
	columns: string[];
};

export type PolicyGroupOption = { id: string; name: string; role: string };

export type AccessDecision = 'allowed' | 'filtered' | 'blocked';

export type AuditStatement = {
	database: string;
	sql: string;
	executed_sql: string | null;
	decision: AccessDecision;
	reason: string;
	policy_ids: string[];
};

export type AccessAuditEntry = {
	id: string;
	created: string | null;
	user_id: string | null;
	user_name: string | null;
	conversation_id: string | null;
	question: string | null;
	sql: string | null;
	decision: AccessDecision;
	reason: string | null;
	policy_ids: string[];
	statements: AuditStatement[];
};

export type VerifiedStatus = 'pending' | 'certified' | 'rejected';

export type VerifiedQuery = {
	id: string;
	question: string;
	sql: string;
	database_name: string | null;
	status: VerifiedStatus;
	source: 'manual' | 'feedback';
	note: string | null;
	created_by: string | null;
	created_by_name: string | null;
	created: string | null;
	reviewed_by: string | null;
	reviewed_by_name: string | null;
	reviewed: string | null;
	has_embedding: boolean;
};
