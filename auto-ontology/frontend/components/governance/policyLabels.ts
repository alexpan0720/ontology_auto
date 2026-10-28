// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { AccessPolicyKind } from '@/types/governance';

/** Short names for badges. */
export const KIND_LABEL: Record<AccessPolicyKind, string> = {
	column: '字段权限',
	mask: '脱敏',
	row: '行权限',
};

/** Names with what the policy does, for choosing one in the policy form. */
export const KIND_DESCRIPTION: Record<AccessPolicyKind, string> = {
	mask: '脱敏（部分遮掩）',
	column: '列权限（拒绝读取）',
	row: '行权限（过滤数据行）',
};
