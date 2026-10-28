// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
	type ReactNode,
} from 'react';
import { usePathname } from 'next/navigation';
import type { BreadcrumbItem } from '@/common/Breadcrumbs';

const SECTION_LABELS: Record<string, string> = {
	'/chat': '对话',
	'/discovery': '发现',
	'/terms': '术语',
	'/analysis': '分析',
	'/exploration': '探索',
	'/data': '全部数据',
	'/analytics': '使用统计',
	'/settings': '设置',
};

const SETTINGS_SECTION_LABELS: Record<string, string> = {
	connections: '数据连接',
	zones: '数据域',
	tags: '标签',
	rules: '规则',
	'semantic-input': '语义输入',
	'glossary-import': '文档提取术语',
	'semantic-compilation': '语义编译',
	pii: '敏感信息设置',
	'agent-settings': '智能体设置',
	bots: '机器人',
	users: '用户',
	'access-control': '数据权限',
	'access-audit': '访问审计',
	'verified-queries': '认证问答库',
	sso: '单点登录',
	'import-export': '导入 / 导出',
};

const EMPTY_TRAIL: BreadcrumbItem[] = [];

const sectionForPath = (path: string): BreadcrumbItem | null => {
	const href = Object.keys(SECTION_LABELS).find(
		(prefix) => path === prefix || path.startsWith(`${prefix}/`),
	);
	const label = href == null ? undefined : SECTION_LABELS[href];
	return href != null && label != null ? { label, href } : null;
};

const crumbsForPath = (path: string): BreadcrumbItem[] => {
	const section = sectionForPath(path);
	if (section == null) return EMPTY_TRAIL;
	if (section.href !== '/settings') return [section];

	const slug = path.split('/')[2];
	const label = slug == null ? undefined : SETTINGS_SECTION_LABELS[slug];
	return label == null ? [section] : [section, { label, href: `/settings/${slug}` }];
};

const trailKey = (items: BreadcrumbItem[]): string =>
	items.map((item) => `${item.label}\u0000${item.href ?? ''}`).join('\u0001');

type BreadcrumbContextValue = {
	items: BreadcrumbItem[];
	setTrail: (items: BreadcrumbItem[]) => void;
	rightSlot: ReactNode;
	setRightSlot: (node: ReactNode) => void;
};

const BreadcrumbContext = createContext<BreadcrumbContextValue>({
	items: EMPTY_TRAIL,
	setTrail: () => {},
	rightSlot: null,
	setRightSlot: () => {},
});

export const BreadcrumbProvider = ({ children }: { children: ReactNode }) => {
	const pathname = usePathname();
	const [prevPath, setPrevPath] = useState<string | null>(null);
	const [routeCrumbs, setRouteCrumbs] = useState<BreadcrumbItem[]>(EMPTY_TRAIL);
	const [trail, setTrailRaw] = useState<BreadcrumbItem[]>(EMPTY_TRAIL);
	const [rightSlot, setRightSlotRaw] = useState<ReactNode>(null);

	const setRightSlot = useCallback((node: ReactNode) => setRightSlotRaw(node), []);

	const setTrail = useCallback((next: BreadcrumbItem[]) => {
		setTrailRaw((prev) => (trailKey(prev) === trailKey(next) ? prev : next));
	}, []);

	if (pathname !== prevPath) {
		const current = crumbsForPath(pathname);
		const parent = prevPath == null ? null : sectionForPath(prevPath);
		const first = current[0];
		setRouteCrumbs(
			first != null && parent != null && parent.href !== first.href
				? [parent, ...current]
				: current,
		);

		setTrailRaw(EMPTY_TRAIL);
		setPrevPath(pathname);
	}

	const items = useMemo(
		() => (trail.length === 0 ? routeCrumbs : [...routeCrumbs, ...trail]),
		[routeCrumbs, trail],
	);

	const value = useMemo(
		() => ({ items, setTrail, rightSlot, setRightSlot }),
		[items, setTrail, rightSlot, setRightSlot],
	);

	return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>;
};

export const useBreadcrumbs = () => useContext(BreadcrumbContext);

export const useBreadcrumbTrail = (items: BreadcrumbItem[]) => {
	const { setTrail } = useBreadcrumbs();

	useEffect(() => {
		setTrail(items);
	});

	useEffect(() => () => setTrail(EMPTY_TRAIL), [setTrail]);
};
