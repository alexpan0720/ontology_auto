// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithCount, ResponseWithError } from './types';
import type {
	AccessAuditEntry,
	AccessDecision,
	AccessPolicy,
	AccessPolicyInput,
	PolicyGroupOption,
	PolicyTableOption,
	VerifiedQuery,
	VerifiedStatus,
} from '@/types/governance';

type Ok = ResponseWithError<{ ok: boolean }>;

export const accessPoliciesApi = {
	list: (): Promise<ResponseWithError<ResponseWithCount<AccessPolicy[]>>> =>
		requests.get('access-policies'),
	options: (): Promise<
		ResponseWithError<{ tables: PolicyTableOption[]; groups: PolicyGroupOption[] }>
	> => requests.get('access-policies/options'),
	create: (input: AccessPolicyInput): Promise<ResponseWithError<{ id: string }>> =>
		requests.post('access-policies', input),
	update: (id: string, changes: Partial<AccessPolicyInput>): Promise<Ok> =>
		requests.patch(`access-policies/${id}`, changes),
	remove: (id: string): Promise<Ok> => requests.delete(`access-policies/${id}`),
	restrictPii: (): Promise<ResponseWithError<{ created: number; skipped_keys: number }>> =>
		requests.post('access-policies/restrict-pii'),
};

export const accessAuditApi = {
	list: (params: {
		decision?: AccessDecision;
		q?: string;
		skip?: number;
		limit?: number;
	}): Promise<ResponseWithError<ResponseWithCount<AccessAuditEntry[]>>> =>
		requests.get('access-audit', params),
};

export type VerifiedInput = {
	question: string;
	sql: string;
	database_name?: string | null;
	note?: string | null;
};

export const verifiedQueriesApi = {
	list: (params: {
		status?: VerifiedStatus;
		q?: string;
	}): Promise<ResponseWithError<ResponseWithCount<VerifiedQuery[]>>> =>
		requests.get('verified-queries', params),
	create: (
		input: VerifiedInput & { status: 'pending' | 'certified' },
	): Promise<ResponseWithError<{ id: string }>> => requests.post('verified-queries', input),
	/** Any signed-in user: lands as `pending` for a reviewer. */
	submit: (input: VerifiedInput): Promise<ResponseWithError<{ id: string }>> =>
		requests.post('verified-queries/submit', input),
	update: (
		id: string,
		changes: Partial<VerifiedInput> & { status?: VerifiedStatus },
	): Promise<Ok> => requests.patch(`verified-queries/${id}`, changes),
	remove: (id: string): Promise<Ok> => requests.delete(`verified-queries/${id}`),
};
