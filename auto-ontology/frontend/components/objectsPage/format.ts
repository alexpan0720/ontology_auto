// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { ObjectValue } from '@/types/objects';

export const formatValue = (value: ObjectValue | undefined): string => {
	if (value === null || value === undefined || value === '') return '—';
	if (typeof value === 'boolean') return value ? '是' : '否';
	return String(value);
};

/** Where an object type's list, or one of its instances, lives. */
export const objectHref = (typeId: string, key?: string | null): string =>
	key == null
		? `/objects?type=${encodeURIComponent(typeId)}`
		: `/objects?type=${encodeURIComponent(typeId)}&key=${encodeURIComponent(key)}`;
