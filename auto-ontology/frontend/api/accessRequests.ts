// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithCount, ResponseWithError } from './types';
import type { AccessRequest, AccessRequestStatus, AccessRestriction } from '@/types/accessRequests';

export const accessRequestsApi = {
	mine: (): Promise<
		ResponseWithError<{ restrictions: AccessRestriction[]; requests: AccessRequest[] }>
	> => requests.get('access-requests/mine'),
	create: (body: {
		policy_id: string;
		reason?: string;
		question?: string;
	}): Promise<ResponseWithError<{ id: string; created: boolean }>> =>
		requests.post('access-requests', body),
	list: (params: {
		status?: AccessRequestStatus;
	}): Promise<ResponseWithError<ResponseWithCount<AccessRequest[]> & { pending: number }>> =>
		requests.get('access-requests', params),
	approve: (
		id: string,
		body: { group_id?: string | null; note?: string },
	): Promise<ResponseWithError<{ ok: boolean; group_id: string }>> =>
		requests.post(`access-requests/${id}/approve`, body),
	reject: (id: string, note?: string): Promise<ResponseWithError<{ ok: boolean }>> =>
		requests.post(`access-requests/${id}/reject`, { note }),
};
