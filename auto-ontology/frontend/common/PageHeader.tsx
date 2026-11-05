// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { ReactNode } from 'react';
import { Icon, type IconName } from '@/common/icons';

export type PageHeaderProps = {
	title: ReactNode;
	/** One sentence on what the page is for, for someone seeing it the first time. */
	description?: ReactNode;
	icon?: IconName;
	/** Buttons or a search box, at the right. */
	actions?: ReactNode;
	/** Under the title row: tabs or filters that belong to the whole page. */
	children?: ReactNode;
};

/**
 * The header every top-level page starts with, so a page says what it is and
 * what it is for in the same place and the same words-to-pixels everywhere.
 */
export const PageHeader = ({ title, description, icon, actions, children }: PageHeaderProps) => (
	<header className="shrink-0 border-b border-zinc-200 bg-white px-6 pt-4 pb-3 dark:border-zinc-800 dark:bg-zinc-950">
		<div className="flex flex-wrap items-start gap-3">
			{icon && (
				<span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#2563eb]/10 text-[#2563eb] dark:bg-[#2563eb]/20 dark:text-[#93c5fd]">
					<Icon name={icon} className="h-[18px] w-[18px]" />
				</span>
			)}
			<div className="min-w-0 flex-1">
				<h1 className="text-lg font-semibold tracking-tight text-heading dark:text-zinc-100">
					{title}
				</h1>
				{description && (
					<p className="mt-0.5 max-w-3xl text-xs text-secondary dark:text-zinc-400">
						{description}
					</p>
				)}
			</div>
			{actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
		</div>
		{children && <div className="mt-3">{children}</div>}
	</header>
);
