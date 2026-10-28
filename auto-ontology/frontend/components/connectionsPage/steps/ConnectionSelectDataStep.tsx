// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import type { ChangeEvent } from 'react';

import { EmptyState } from '@/common/EmptyState';
import { IconName } from '@/common/icons';
import { EmptyStateVariant } from '@/enums/emptyState';

export type ConnectionSelectDataStepProps = {
	availableDatabases: string[];
	selectedDatabases: string[];
	onSelectionChange: (databases: string[]) => void;
};

export const ConnectionSelectDataStep = ({
	availableDatabases,
	selectedDatabases,
	onSelectionChange,
}: ConnectionSelectDataStepProps) => {
	if (availableDatabases.length === 0) {
		return (
			<EmptyState
				variant={EmptyStateVariant.Borderless}
				icon={IconName.Database}
				title="没有可选的数据库"
				description="此连接下没有发现数据库。仍可先创建连接，稍后再导入。"
				className="min-h-[360px]"
			/>
		);
	}

	const toggle =
		(name: string) =>
		({ target }: ChangeEvent<HTMLInputElement>) => {
			if (target.checked) {
				onSelectionChange([...selectedDatabases, name]);
			} else {
				onSelectionChange(selectedDatabases.filter((d) => d !== name));
			}
		};

	return (
		<div className="flex flex-col gap-2 p-2">
			<p className="text-sm text-body dark:text-zinc-400">
				选择要纳入目录的数据库或 schema。
			</p>
			<ul className="flex max-h-[360px] flex-col gap-1 overflow-y-auto rounded-lg border border-zinc-200 p-2 dark:border-zinc-700">
				{availableDatabases.map((name) => (
					<li key={name}>
						<label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/80">
							<input
								type="checkbox"
								checked={selectedDatabases.includes(name)}
								onChange={toggle(name)}
								className="h-4 w-4 rounded border-zinc-300 text-[#2563eb] focus:ring-[#2563eb]/30"
							/>
							<span className="text-sm text-heading dark:text-zinc-200">{name}</span>
						</label>
					</li>
				))}
			</ul>
		</div>
	);
};
