// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { Metadata } from 'next';
import { AnalyticsView } from '@/components/analyticsPage';

export const metadata: Metadata = {
	title: '使用统计',
};

// Usage is part of running the question service, so it lives in the admin
// centre (whose layout already requires an admin) instead of the main nav.
export default function UsagePage() {
	return <AnalyticsView />;
}
