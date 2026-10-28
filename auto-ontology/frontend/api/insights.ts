// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithError } from './types';
import type { InsightBoard } from '@/types/insights';

export const insightsApi = {
	board: (days: number): Promise<ResponseWithError<InsightBoard>> =>
		requests.get('insights', { days }),
	dismiss: (key: string): Promise<ResponseWithError<{ ok: boolean }>> =>
		requests.post('insights/dismiss', { key }),
	undismiss: (key: string): Promise<ResponseWithError<{ ok: boolean }>> =>
		requests.delete(`insights/dismiss/${encodeURIComponent(key)}`),
};
