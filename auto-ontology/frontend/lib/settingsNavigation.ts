// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/**
 * The admin centre's sections, as data: its side menu and its overview page
 * both render from here. Grouped by the job at hand — setting the data up,
 * deciding who sees what, keeping answers good, connecting other tools —
 * so one-off setup is not interleaved with daily review work.
 */

export type SettingsItem = {
	label: string;
	href: string;
	/** What the page is for, on the overview. */
	description: string;
};

export type SettingsGroup = {
	key: string;
	title: string;
	items: SettingsItem[];
};

export const SETTINGS_OVERVIEW_HREF = '/settings';
export const CONNECTIONS_HREF = '/settings/connections';

export const SETTINGS_GROUPS: SettingsGroup[] = [
	{
		key: 'setup',
		title: '接入与建模',
		items: [
			{ label: '数据连接', href: CONNECTIONS_HREF, description: '接入要问数的数据库' },
			{
				label: '语义编译',
				href: '/settings/semantic-compilation',
				description: '从元数据生成语义层',
			},
			{
				label: '对象类型',
				href: '/settings/object-types',
				description: '定义客户、订单等业务对象',
			},
			{
				label: '语义输入',
				href: '/settings/semantic-input',
				description: '补充业务背景和口径说明',
			},
			{
				label: '文档提取术语',
				href: '/settings/glossary-import',
				description: '从文档批量导入术语',
			},
			{ label: '数据域', href: '/settings/zones', description: '按业务范围划分数据' },
			{ label: '标签', href: '/settings/tags', description: '给数据和术语打标签' },
			{ label: '规则', href: '/settings/rules', description: '按搜索条件自动打标签' },
		],
	},
	{
		key: 'security',
		title: '权限与安全',
		items: [
			{
				label: '用户与用户组',
				href: '/settings/users',
				description: '邀请成员，管理角色和分组',
			},
			{
				label: '数据权限',
				href: '/settings/access-control',
				description: '行、列和脱敏策略',
			},
			{
				label: '权限申请',
				href: '/settings/access-requests',
				description: '审批成员的数据访问申请',
			},
			{ label: '敏感信息', href: '/settings/pii', description: '识别和保护个人信息' },
			{
				label: '访问审计',
				href: '/settings/access-audit',
				description: '每次查询的放行与拦截记录',
			},
			{ label: '单点登录', href: '/settings/sso', description: '接入企业身份提供方' },
		],
	},
	{
		key: 'quality',
		title: '问数运营',
		items: [
			{
				label: '认证问答库',
				href: '/settings/verified-queries',
				description: '审核并认证标准问答',
			},
			{ label: '问数质量', href: '/settings/insights', description: '没答好的问题和原因' },
			{ label: '使用统计', href: '/settings/usage', description: '谁在问、问了多少' },
			{
				label: '智能体设置',
				href: '/settings/agent-settings',
				description: '问数智能体的提示与行为',
			},
		],
	},
	{
		key: 'integrations',
		title: '集成',
		items: [
			{
				label: '订阅与预警',
				href: '/settings/subscriptions',
				description: '定时推送指标，异常时预警',
			},
			{ label: '机器人', href: '/settings/bots', description: '在钉钉、飞书里问数' },
			{
				label: '导入 / 导出',
				href: '/settings/import-export',
				description: '迁移或备份语义模型',
			},
		],
	},
];

/**
 * The groups an admin is shown. Connections set by environment variable cannot
 * be edited here, so their page is left out rather than shown read-only.
 */
export const visibleSettingsGroups = (connectionsEnvManaged: boolean): SettingsGroup[] =>
	SETTINGS_GROUPS.map((group) => ({
		...group,
		items: group.items.filter(
			(item) => !(connectionsEnvManaged && item.href === CONNECTIONS_HREF),
		),
	}));

/** The overview is selected only on itself; every other page on its subtree. */
export const isSettingsHrefActive = (pathname: string, href: string): boolean =>
	href === SETTINGS_OVERVIEW_HREF
		? pathname === href
		: pathname === href || pathname.startsWith(`${href}/`);
