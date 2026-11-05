// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { Suspense } from 'react';
import type { Metadata } from 'next';

import { IconName } from '@/common/icons';
import { PageHeader } from '@/common/PageHeader';
import { ExplorationView } from '@/components/explorationPage';
import { ExplorationLoader } from '@/components/explorationPage/ExplorationLoader';

export const metadata: Metadata = {
	title: '关系图谱',
};

export default function ExplorationPage() {
	return (
		<div className="flex h-full flex-col">
			<PageHeader
				title="关系图谱"
				description="以图的方式查看表、字段和业务术语之间的关联，点击节点可展开相邻的数据。"
				icon={IconName.Exploration}
			/>
			<div className="min-h-0 flex-1">
				<Suspense fallback={<ExplorationLoader />}>
					<ExplorationView />
				</Suspense>
			</div>
		</div>
	);
}
