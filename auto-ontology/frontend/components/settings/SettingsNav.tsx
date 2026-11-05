// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
	SETTINGS_OVERVIEW_HREF,
	isSettingsHrefActive,
	visibleSettingsGroups,
} from '@/lib/settingsNavigation';

function rowClassName(selected: boolean) {
	return `flex min-h-9 items-center rounded-lg px-3 text-sm no-underline transition-colors ${
		selected
			? 'bg-[#2563eb]/15 font-medium text-heading shadow-sm ring-1 ring-[#2563eb]/30 dark:text-zinc-100'
			: 'text-heading hover:bg-zinc-100/90 dark:text-zinc-200 dark:hover:bg-zinc-800/70'
	}`;
}

export type SettingsNavProps = {
	/**
	 * Connections come from the CONNECTION_STRINGS env var, so they are fixed by
	 * config and the section is dropped. Resolved by the server layout rather
	 * than fetched here: a client-side lookup rendered the link for as long as
	 * the request took, then took it away again.
	 */
	connectionsEnvManaged: boolean;
};

// The whole admin centre is admin-only (gated in app/settings/layout.tsx), so
// no per-item role checks are needed here.
export const SettingsNav = ({ connectionsEnvManaged }: SettingsNavProps) => {
	const pathname = usePathname() ?? '';

	return (
		<nav
			className="flex min-h-0 flex-1 flex-col gap-y-4 overflow-y-auto px-3 py-2 sm:px-4"
			aria-label="管理中心菜单"
		>
			<Link
				href={SETTINGS_OVERVIEW_HREF}
				aria-current={
					isSettingsHrefActive(pathname, SETTINGS_OVERVIEW_HREF) ? 'page' : undefined
				}
				className={rowClassName(isSettingsHrefActive(pathname, SETTINGS_OVERVIEW_HREF))}
			>
				总览
			</Link>
			{visibleSettingsGroups(connectionsEnvManaged).map((group) => (
				<div key={group.key} role="group" aria-labelledby={`settings-nav-${group.key}`}>
					<p
						id={`settings-nav-${group.key}`}
						className="px-3 pb-1 text-[11px] font-medium tracking-wide text-secondary dark:text-zinc-500"
					>
						{group.title}
					</p>
					<div className="flex flex-col gap-y-1">
						{group.items.map((item) => {
							const selected = isSettingsHrefActive(pathname, item.href);
							return (
								<Link
									key={item.href}
									href={item.href}
									aria-current={selected ? 'page' : undefined}
									className={rowClassName(selected)}
								>
									{item.label}
								</Link>
							);
						})}
					</div>
				</div>
			))}
		</nav>
	);
};
