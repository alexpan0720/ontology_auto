// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

type NavItem = { label: string; href: string };

const CONNECTIONS_NAV_ITEM: NavItem = { label: '数据连接', href: '/settings/connections' };
const ZONES_NAV_ITEM: NavItem = { label: '数据域', href: '/settings/zones' };
const TAGS_NAV_ITEM: NavItem = { label: '标签', href: '/settings/tags' };
const RULES_NAV_ITEM: NavItem = { label: '规则', href: '/settings/rules' };
const PII_SETTINGS_NAV_ITEM: NavItem = {
	label: '敏感信息设置',
	href: '/settings/pii',
};
const SEMANTIC_INPUT_NAV_ITEM: NavItem = {
	label: '语义输入',
	href: '/settings/semantic-input',
};
const USERS_NAV_ITEM: NavItem = { label: '用户', href: '/settings/users' };
const SSO_NAV_ITEM: NavItem = { label: '单点登录', href: '/settings/sso' };
const SEMANTIC_COMPILATION_NAV_ITEM: NavItem = {
	label: '语义编译',
	href: '/settings/semantic-compilation',
};
const AGENT_SETTINGS_NAV_ITEM: NavItem = {
	label: '智能体设置',
	href: '/settings/agent-settings',
};
const ACCESS_CONTROL_NAV_ITEM: NavItem = {
	label: '数据权限',
	href: '/settings/access-control',
};
const ACCESS_AUDIT_NAV_ITEM: NavItem = {
	label: '访问审计',
	href: '/settings/access-audit',
};
const VERIFIED_QUERIES_NAV_ITEM: NavItem = {
	label: '认证问答库',
	href: '/settings/verified-queries',
};
const GLOSSARY_IMPORT_NAV_ITEM: NavItem = {
	label: '文档提取术语',
	href: '/settings/glossary-import',
};
const ACCESS_REQUESTS_NAV_ITEM: NavItem = { label: '权限申请', href: '/settings/access-requests' };
const INSIGHTS_NAV_ITEM: NavItem = { label: '问数质量', href: '/settings/insights' };
const SUBSCRIPTIONS_NAV_ITEM: NavItem = { label: '订阅与预警', href: '/settings/subscriptions' };
const BOTS_NAV_ITEM: NavItem = { label: '机器人', href: '/settings/bots' };
const IMPORT_EXPORT_NAV_ITEM: NavItem = {
	label: '导入 / 导出',
	href: '/settings/import-export',
};

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

// The whole Settings section is admin-only (gated in app/settings/layout.tsx),
// so no per-item role checks are needed here.
export const SettingsNav = ({ connectionsEnvManaged }: SettingsNavProps) => {
	const pathname = usePathname();

	const items: NavItem[] = [];
	if (!connectionsEnvManaged) items.push(CONNECTIONS_NAV_ITEM);
	items.push(
		ZONES_NAV_ITEM,
		TAGS_NAV_ITEM,
		RULES_NAV_ITEM,
		PII_SETTINGS_NAV_ITEM,
		SEMANTIC_INPUT_NAV_ITEM,
		GLOSSARY_IMPORT_NAV_ITEM,
		USERS_NAV_ITEM,
		ACCESS_CONTROL_NAV_ITEM,
		ACCESS_REQUESTS_NAV_ITEM,
		ACCESS_AUDIT_NAV_ITEM,
		VERIFIED_QUERIES_NAV_ITEM,
		INSIGHTS_NAV_ITEM,
		SSO_NAV_ITEM,
		SEMANTIC_COMPILATION_NAV_ITEM,
		AGENT_SETTINGS_NAV_ITEM,
		BOTS_NAV_ITEM,
		SUBSCRIPTIONS_NAV_ITEM,
		IMPORT_EXPORT_NAV_ITEM,
	);

	return (
		<nav
			className="flex min-h-0 flex-1 flex-col gap-y-1 overflow-y-auto px-3 py-2 sm:px-4"
			aria-label="设置分类"
		>
			{items.map((item) => {
				const selected = pathname === item.href || pathname.startsWith(`${item.href}/`);
				return (
					<Link key={item.href} href={item.href} className={rowClassName(selected)}>
						{item.label}
					</Link>
				);
			})}
		</nav>
	);
};
