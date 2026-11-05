// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { IconName } from '@/common/icons';

/**
 * The app's navigation, as data: the sidebar renders it, and tests pin who
 * sees what. Grouped by what a person came to do — ask and look first, the
 * data assets behind the answers next, administration last — rather than by
 * how the backend is split.
 */

export type NavItem = {
	key: string;
	label: string;
	href: string;
	icon: IconName;
	/** One line under the label where there is room for it (the home page cards). */
	hint?: string;
	/** Other routes that belong to this item, so it stays highlighted there. */
	alsoActiveOn?: string[];
};

export type NavSection = {
	key: string;
	/** Absent for the first section, which needs no heading. */
	title?: string;
	adminOnly?: boolean;
	items: NavItem[];
};

export const NAV_SECTIONS: NavSection[] = [
	{
		key: 'main',
		items: [
			{ key: 'home', label: '首页', href: '/home', icon: IconName.Home },
			{
				key: 'chat',
				label: '问数',
				href: '/chat',
				icon: IconName.ChatBubble,
				hint: '用自然语言提问，直接得到数据和图表',
			},
			{
				key: 'objects',
				label: '业务对象',
				href: '/objects',
				icon: IconName.Cube,
				hint: '按客户、订单等业务对象查看数据和关联',
			},
			{
				key: 'terms',
				label: '业务词典',
				href: '/terms',
				icon: IconName.Terms,
				hint: '业务术语和指标的统一口径',
			},
		],
	},
	{
		key: 'assets',
		title: '数据资产',
		items: [
			{
				key: 'data',
				label: '数据目录',
				href: '/data',
				icon: IconName.Database,
				hint: '数据库、表和字段',
				// Full search results live under the catalog they search.
				alsoActiveOn: ['/discovery'],
			},
			{
				key: 'exploration',
				label: '关系图谱',
				href: '/exploration',
				icon: IconName.Exploration,
				hint: '表与术语之间的关系图',
			},
			{
				key: 'analysis',
				label: '已保存查询',
				href: '/analysis',
				icon: IconName.ChartBar,
				hint: '团队沉淀的 SQL 与预测查询',
			},
		],
	},
	{
		key: 'admin',
		title: '管理',
		adminOnly: true,
		items: [
			{
				key: 'settings',
				label: '管理中心',
				href: '/settings',
				icon: IconName.Settings,
				hint: '接入、权限、问数运营与集成',
				alsoActiveOn: ['/analytics'],
			},
		],
	},
];

/** The sections a viewer or an admin is shown. */
export const visibleNavSections = (isAdmin: boolean): NavSection[] =>
	NAV_SECTIONS.filter((section) => isAdmin || !section.adminOnly);

const isUnder = (pathname: string, href: string): boolean =>
	pathname === href || pathname.startsWith(`${href}/`);

export const isNavItemActive = (pathname: string, item: NavItem): boolean =>
	isUnder(pathname, item.href) ||
	(item.alsoActiveOn ?? []).some((href) => isUnder(pathname, href));

/** A nav item by key, for pages that link to a section by name. */
export const navItem = (key: string): NavItem => {
	const found = NAV_SECTIONS.flatMap((section) => section.items).find((item) => item.key === key);
	if (!found) throw new Error(`Unknown nav item: ${key}`);
	return found;
};
