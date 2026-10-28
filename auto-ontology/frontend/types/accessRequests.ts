// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/server/access_requests/router.py`. */

import type { AccessPolicyKind } from './governance';

export type AccessRequestStatus = 'pending' | 'approved' | 'rejected';

/** A policy that keeps something from the current user. */
export type AccessRestriction = {
	policy_id: string;
	kind: AccessPolicyKind;
	database_name: string;
	/** `schema.table.column`, or `schema.table` for a row policy. */
	target: string;
	column_name: string | null;
	effect: string;
	description: string | null;
	pending_request_id: string | null;
};

export type AccessRequest = {
	id: string;
	user_id: string;
	user_name: string;
	user_email: string | null;
	policy_id: string;
	kind: AccessPolicyKind | null;
	target: string | null;
	effect: string | null;
	reason: string | null;
	question: string | null;
	status: AccessRequestStatus;
	decided_by: string | null;
	decided_by_name: string | null;
	decided: string | null;
	decision_note: string | null;
	granted_group_id: string | null;
	granted_group_name: string | null;
	policy_group_ids: string[];
	created: string | null;
};
