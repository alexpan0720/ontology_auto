// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { Suspense } from 'react';
import { IconName } from '@/common/icons';
import { PageHeader } from '@/common/PageHeader';
import { SkeletonBlock, SkeletonCard, SkeletonRows } from '@/common/Skeleton';
import { DataWorkspaceView } from '@/components/dataPage';

export default function DataPage() {
	return (
		<div className="flex h-full flex-col">
			<PageHeader
				title="数据目录"
				description="已接入的数据库、表和字段，以及它们的说明、样例值和标签。"
				icon={IconName.Database}
			/>
			<div className="min-h-0 flex-1">
				<Suspense
					fallback={
						<div className="flex h-full" role="status" aria-label="正在加载数据工作区">
							<aside className="w-72 border-r border-zinc-200 p-4 dark:border-zinc-800">
								<SkeletonBlock className="mb-5 h-6 w-24" />
								<SkeletonRows rows={8} />
							</aside>
							<main className="flex flex-1 flex-col gap-4 p-6">
								<SkeletonCard rows={4} />
								<SkeletonCard rows={4} />
							</main>
						</div>
					}
				>
					<DataWorkspaceView />
				</Suspense>
			</div>
		</div>
	);
}
