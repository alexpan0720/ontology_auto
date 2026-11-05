// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, IconName } from '@/common/icons';
import { isNavItemActive, visibleNavSections } from '@/lib/navigation';

/** Where the collapsed/expanded choice is remembered, per browser. */
export const SIDEBAR_COLLAPSED_KEY = 'ao.sidebar.collapsed';

const readCollapsed = (): boolean => {
	try {
		return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
	} catch {
		return false;
	}
};

const writeCollapsed = (collapsed: boolean): void => {
	try {
		window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0');
	} catch {
		// Storage can be unavailable (private windows); the choice just isn't kept.
	}
};

/**
 * The app's sidebar: labelled, grouped by task, and collapsible to icons.
 *
 * Labels are always shown when expanded — the previous icon-only rail made
 * people hover to learn where they were going. Collapsing is remembered per
 * browser for those who know the icons.
 */
export const NavRail = ({ isAdmin = false }: { isAdmin?: boolean }) => {
	const pathname = usePathname() ?? '';
	const [collapsed, setCollapsed] = useState(false);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- storage is only readable after hydration
		setCollapsed(readCollapsed());
	}, []);

	const toggle = () => {
		setCollapsed((current) => {
			writeCollapsed(!current);
			return !current;
		});
	};

	return (
		<nav
			aria-label="主导航"
			className={`flex h-full shrink-0 flex-col border-r border-zinc-200 bg-white py-3 transition-[width] duration-200 dark:border-zinc-800 dark:bg-zinc-950 ${
				collapsed ? 'w-14' : 'w-52'
			}`}
		>
			<div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-2">
				{visibleNavSections(isAdmin).map((section) => (
					<div key={section.key} role="group" aria-label={section.title ?? '常用'}>
						{section.title &&
							(collapsed ? (
								<div className="mx-2 mb-2 border-t border-zinc-200 dark:border-zinc-800" />
							) : (
								<p className="mb-1 px-2 text-[11px] font-medium tracking-wide text-secondary dark:text-zinc-500">
									{section.title}
								</p>
							))}
						<ul className="flex flex-col gap-0.5">
							{section.items.map((item) => {
								const active = isNavItemActive(pathname, item);
								return (
									<li key={item.key}>
										<Link
											href={item.href}
											title={collapsed ? item.label : undefined}
											aria-current={active ? 'page' : undefined}
											className={`flex h-9 items-center gap-3 rounded-lg text-sm transition-colors ${
												collapsed ? 'justify-center' : 'px-2.5'
											} ${
												active
													? 'bg-[#2563eb]/10 font-medium text-[#1d4ed8] dark:bg-[#2563eb]/20 dark:text-[#93c5fd]'
													: 'text-body hover:bg-zinc-100 hover:text-heading dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100'
											}`}
										>
											<Icon name={item.icon} className="h-5 w-5 shrink-0" />
											{!collapsed && (
												<span className="truncate">{item.label}</span>
											)}
										</Link>
									</li>
								);
							})}
						</ul>
					</div>
				))}
			</div>
			<div className="px-2 pt-2">
				<button
					type="button"
					onClick={toggle}
					aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
					title={collapsed ? '展开侧边栏' : '收起侧边栏'}
					className={`flex h-9 w-full items-center gap-3 rounded-lg text-xs text-secondary hover:bg-zinc-100 hover:text-heading dark:hover:bg-zinc-800 dark:hover:text-zinc-100 ${
						collapsed ? 'justify-center' : 'px-2.5'
					}`}
				>
					<Icon name={IconName.Sidebar} className="h-5 w-5 shrink-0" />
					{!collapsed && <span>收起</span>}
				</button>
			</div>
		</nav>
	);
};
