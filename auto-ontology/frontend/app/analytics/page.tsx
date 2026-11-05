// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { redirect } from 'next/navigation';

// Usage moved into the admin centre; old links and bookmarks still land there.
export default function AnalyticsPage() {
	redirect('/settings/usage');
}
