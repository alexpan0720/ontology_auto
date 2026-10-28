// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';
import { requireUser } from '@/auth/auth-guards';
import { userCan } from '@/auth/permissions';
import { MyAccessRequestsView } from '@/components/accessRequests/MyAccessRequestsView';

export const metadata: Metadata = {
	title: '我的权限申请',
};

export default async function MyAccessRequestsPage() {
	const session = await requireUser();
	const allowed = userCan(
		{ id: session.user.id, role: session.user.role ?? null },
		{ accessRequest: ['submit'] },
	);
	if (!allowed) redirect('/chat');
	return (
		<Suspense>
			<MyAccessRequestsView />
		</Suspense>
	);
}
