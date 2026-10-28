// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { BADGE_TONE } from '@/components/settings/pageStyles';
import type { AccessRequestStatus } from '@/types/accessRequests';

export const STATUS_BADGE: Record<
	AccessRequestStatus,
	{ label: string; tone: keyof typeof BADGE_TONE }
> = {
	pending: { label: '待审批', tone: 'amber' },
	approved: { label: '已批准', tone: 'green' },
	rejected: { label: '已驳回', tone: 'grey' },
};
