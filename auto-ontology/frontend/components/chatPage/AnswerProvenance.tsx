// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { attributePath, catalogPath, focusUrl } from '@/app/settings/tags/tag-item-path';
import { CertificationBadge } from '@/common/CertificationBadge';
import { Icon, IconName } from '@/common/icons';
import { CertificationStatus } from '@/enums/certification';
import type { AnswerProvenance as Provenance, ProvenanceItem } from '@/types/chat';

type Item = ProvenanceItem & { score?: number };

type Group = {
	key: keyof Provenance;
	label: string;
	unit: string;
	href: (item: Item) => string | null;
	detail?: (item: Item) => string | undefined;
};

/** A group's items; certified Q&A carry no status of their own and are certified by definition. */
const itemsOf = (provenance: Provenance, key: keyof Provenance): Item[] =>
	(provenance[key] ?? []).map((item) => ({
		...item,
		status: item.status ?? CertificationStatus.Certified,
	}));

/** Ordered from what was queried down to the business meaning laid over it. */
const GROUPS: Group[] = [
	{
		key: 'tables',
		label: '查询的数据表',
		unit: '张表',
		href: (t) => catalogPath(t.database_id, t.schema_id, t.id),
		detail: (t) => (t.schema_name ? `${t.schema_name}.${t.name}` : undefined),
	},
	{
		key: 'sql_attributes',
		label: '指标（SQL 属性）',
		unit: '个指标',
		href: (a) => attributePath('sqlAttr', a.term_id, a.id),
	},
	{
		key: 'column_attributes',
		label: '列属性',
		unit: '个列属性',
		href: (a) => attributePath('colAttr', a.term_id, a.id),
	},
	{
		key: 'terms',
		label: '业务术语',
		unit: '个术语',
		href: (t) => focusUrl('/terms', t.id),
	},
	{
		key: 'verified_queries',
		label: '参考的认证问答',
		unit: '条认证问答',
		href: () => null,
		detail: (q) =>
			q.score != null ? `${q.name}（相似度 ${Math.round(q.score * 100)}%）` : undefined,
	},
];

const ProvenanceRow = ({ item, group }: { item: Item; group: Group }) => {
	const href = group.href(item);
	const detail = group.detail?.(item);
	const name = (
		<span className="truncate" title={detail ?? item.name}>
			{detail ?? item.name}
		</span>
	);
	return (
		<li className="flex min-w-0 items-center gap-1.5 text-xs">
			<CertificationBadge status={item.status} iconOnly focusable={false} />
			{href ? (
				<Link
					href={href}
					className="min-w-0 truncate text-body hover:text-[#2563eb] hover:underline dark:text-zinc-300 dark:hover:text-[#60a5fa]"
				>
					{name}
				</Link>
			) : (
				<span className="min-w-0 truncate text-body dark:text-zinc-300">{name}</span>
			)}
		</li>
	);
};

/**
 * "What this answer stands on": the tables its SQL read and the semantic objects
 * defined over them, each with its certification, linking to its own page.
 * Collapsed to a one-line summary so it never crowds the answer itself.
 */
export const AnswerProvenance = ({
	provenance,
	className = '',
}: {
	provenance: Provenance;
	className?: string;
}) => {
	const [open, setOpen] = useState(false);
	const groups = GROUPS.filter((g) => itemsOf(provenance, g.key).length > 0);
	if (groups.length === 0) return null;

	const items = groups.flatMap((g) => itemsOf(provenance, g.key));
	const certified = items.filter((i) => i.status === CertificationStatus.Certified).length;
	const summary = groups.map((g) => `${itemsOf(provenance, g.key).length} ${g.unit}`).join(' · ');
	const allCertified = certified === items.length;

	return (
		<div
			className={`rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900 ${className}`}
		>
			<button
				type="button"
				onClick={() => setOpen((v) => !v)}
				aria-expanded={open}
				className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs"
			>
				<Icon
					name={IconName.ChevronRight}
					aria-hidden
					className={`h-3.5 w-3.5 shrink-0 text-secondary transition-transform ${open ? 'rotate-90' : ''}`}
				/>
				<span className="font-medium text-heading dark:text-zinc-100">回答依据</span>
				<span className="min-w-0 truncate text-secondary dark:text-zinc-400">
					{summary}
				</span>
				<span
					className={`ml-auto shrink-0 whitespace-nowrap ${
						allCertified
							? 'text-[#2563eb] dark:text-[#60a5fa]'
							: 'text-secondary dark:text-zinc-400'
					}`}
				>
					已认证 {certified}/{items.length}
				</span>
			</button>
			{open && (
				<div className="flex flex-col gap-3 border-t border-zinc-200 px-3 py-2.5 dark:border-zinc-700">
					{groups.map((group) => (
						<section key={group.key}>
							<h4 className="mb-1 text-[11px] font-medium text-secondary dark:text-zinc-400">
								{group.label}
							</h4>
							<ul className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
								{itemsOf(provenance, group.key).map((item) => (
									<ProvenanceRow key={item.id} item={item} group={group} />
								))}
							</ul>
						</section>
					))}
					<p className="text-[11px] text-secondary dark:text-zinc-500">
						数据表来自实际执行的
						SQL；指标、列属性和术语是定义在这些表上的语义对象。未认证的定义建议核对后再使用结果。
					</p>
				</div>
			)}
		</div>
	);
};
