// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { accessRequestsApi } from '@/api/accessRequests';
import { verifiedQueriesApi } from '@/api/governance';
import { insightsApi } from '@/api/insights';
import { objectTypesApi } from '@/api/objects';
import { semanticCompilationApi } from '@/api/settings';

/** One thing an admin may need to act on, and where to act on it. */
export type Todo = {
	key: string;
	label: string;
	href: string;
	/** `null` while loading or when it could not be read. */
	count: number | null;
	/** What the count means, under it. */
	unit: string;
	/** A state rather than a count (the semantic layer). Wins over `count`. */
	status?: { text: string; tone: 'ok' | 'warn' };
};

const INSIGHT_DAYS = 7;

/** Each read on its own: one failing source leaves the other cards standing. */
const readTodos = async (): Promise<Todo[]> => {
	const settled = await Promise.allSettled([
		accessRequestsApi.list({ status: 'pending' }),
		objectTypesApi.list('candidate'),
		verifiedQueriesApi.list({ status: 'pending' }),
		insightsApi.board(INSIGHT_DAYS),
		semanticCompilationApi.getStatus(),
	]);
	const [requests, objects, verified, insights, semantic] = settled;

	const ok = <T,>(result: PromiseSettledResult<T>): T | null =>
		result.status === 'fulfilled' && !(result.value as { error?: boolean } | null)?.error
			? result.value
			: null;

	const requestsRes = ok(requests);
	const objectsRes = ok(objects);
	const verifiedRes = ok(verified);
	const insightsRes = ok(insights);
	const semanticRes = ok(semantic);

	return [
		{
			key: 'access-requests',
			label: '待审批的权限申请',
			href: '/settings/access-requests',
			count: requestsRes ? requestsRes.pending : null,
			unit: '个申请',
		},
		{
			key: 'object-candidates',
			label: '待确认的业务对象',
			href: '/settings/object-types',
			count: objectsRes
				? objectsRes.summary.candidate_types + objectsRes.summary.candidate_links
				: null,
			unit: '个对象或关系',
		},
		{
			key: 'verified-queries',
			label: '待审核的认证问答',
			href: '/settings/verified-queries',
			count: verifiedRes ? verifiedRes.count : null,
			unit: '条提交',
		},
		{
			key: 'insights',
			label: `近 ${INSIGHT_DAYS} 天没答好的问题`,
			href: '/settings/insights',
			count: insightsRes ? insightsRes.groups.length : null,
			unit: '类问题',
		},
		{
			key: 'semantic',
			label: '语义层',
			href: '/settings/semantic-compilation',
			count: null,
			unit: '',
			status: semanticRes
				? semanticRes.running
					? { text: '正在编译', tone: 'warn' }
					: semanticRes.calculated
						? { text: '已就绪', tone: 'ok' }
						: { text: '尚未编译', tone: 'warn' }
				: undefined,
		},
	];
};

export const useAdminTodos = (): Todo[] | null => {
	const [todos, setTodos] = useState<Todo[] | null>(null);
	useEffect(() => {
		let active = true;
		void readTodos().then((rows) => {
			if (active) setTodos(rows);
		});
		return () => {
			active = false;
		};
	}, []);
	return todos;
};

const TONE = {
	ok: 'text-emerald-600 dark:text-emerald-400',
	warn: 'text-amber-600 dark:text-amber-400',
} as const;

export const TodoCard = ({ todo }: { todo: Todo }) => {
	const needsAction = todo.status ? todo.status.tone === 'warn' : (todo.count ?? 0) > 0;
	return (
		<Link
			href={todo.href}
			className={`block rounded-xl border p-3.5 transition-colors hover:border-[#2563eb]/50 ${
				needsAction
					? 'border-amber-200 bg-amber-50/60 dark:border-amber-500/30 dark:bg-amber-500/5'
					: 'border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900'
			}`}
		>
			<p className="text-xs text-secondary dark:text-zinc-400">{todo.label}</p>
			{todo.status ? (
				<p className={`mt-1 text-base font-semibold ${TONE[todo.status.tone]}`}>
					{todo.status.text}
				</p>
			) : (
				<p className="mt-1 text-xl font-semibold text-heading dark:text-zinc-100">
					{todo.count ?? '—'}
					{todo.count !== null && (
						<span className="ml-1 text-xs font-normal text-secondary">{todo.unit}</span>
					)}
				</p>
			)}
		</Link>
	);
};

/** The admin's to-do row, on the home page and the admin centre overview. */
export const AdminTodos = ({ linkToSettings = true }: { linkToSettings?: boolean }) => {
	const todos = useAdminTodos();
	return (
		<section aria-labelledby="home-todos">
			<div className="mb-2 flex items-center justify-between">
				<h2
					id="home-todos"
					className="text-sm font-semibold text-heading dark:text-zinc-100"
				>
					管理待办
				</h2>
				{linkToSettings && (
					<Link href="/settings" className="text-xs text-secondary hover:text-[#1d4ed8]">
						进入管理中心
					</Link>
				)}
			</div>
			<div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
				{(todos ?? []).map((todo) => (
					<TodoCard key={todo.key} todo={todo} />
				))}
				{todos === null &&
					Array.from({ length: 5 }, (_, i) => (
						<div
							key={i}
							aria-hidden
							className="h-[74px] animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-800"
						/>
					))}
			</div>
		</section>
	);
};
