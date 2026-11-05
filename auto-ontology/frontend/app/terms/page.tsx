// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { Suspense } from 'react';
import type { Metadata } from 'next';
import { IconName } from '@/common/icons';
import { PageHeader } from '@/common/PageHeader';
import { TermsLoadingSkeleton, TermsView } from '@/components/termsPage';

export const metadata: Metadata = {
	title: '业务词典',
};

export default function TermsPage() {
	return (
		<Suspense
			fallback={
				<div className="flex h-full w-full flex-col bg-white dark:bg-zinc-950">
					<PageHeader title="业务词典" icon={IconName.Terms} />
					<div className="flex-1 px-6 py-6">
						<TermsLoadingSkeleton />
					</div>
				</div>
			}
		>
			<TermsView />
		</Suspense>
	);
}
