// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { Metadata } from 'next';
import { requireUser } from '@/auth/auth-guards';
import { HomeView } from '@/components/homePage/HomeView';
import { Role } from '@/enums/auth';

export const metadata: Metadata = {
	title: '首页',
};

export default async function HomePage() {
	const session = await requireUser();
	return <HomeView userName={session.user.name} isAdmin={session.user.role === Role.Admin} />;
}
