// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithError } from './types';
import type { BotPlatform, BotSettings } from '@/types/bots';

export const botsApi = {
	list: (): Promise<ResponseWithError<{ data: BotSettings[] }>> => requests.get('bots'),
	save: (
		platform: BotPlatform,
		body: { enabled: boolean; app_id: string; app_secret?: string },
	): Promise<ResponseWithError<BotSettings>> => requests.put(`bots/${platform}`, body),
	test: (
		platform: BotPlatform,
		body: { app_id: string; app_secret?: string },
	): Promise<ResponseWithError<{ ok: boolean; message: string }>> =>
		requests.post(`bots/${platform}/test`, body),
};
