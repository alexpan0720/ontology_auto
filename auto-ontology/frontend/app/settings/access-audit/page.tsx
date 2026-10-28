// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { accessAuditApi } from '@/api/governance';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { ButtonTheme, Size } from '@/enums/button';
import type { AccessAuditEntry, AccessDecision } from '@/types/governance';
import { INPUT_FILTER, PAGE_MAIN } from '@/components/settings/pageStyles';

const PAGE_SIZE = 30;

const DECISION_LABEL: Record<AccessDecision, string> = {
	allowed: '允许',
	filtered: '已过滤',
	blocked: '已拦截',
};

const DECISION_CLASS: Record<AccessDecision, string> = {
	allowed: 'bg-zinc-100 text-secondary dark:bg-zinc-800 dark:text-zinc-400',
	filtered: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
	blocked: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
};

const csvCell = (value: unknown): string => `"${String(value ?? '').replace(/"/g, '""')}"`;

const downloadCsv = (rows: AccessAuditEntry[]) => {
	const header = ['时间', '用户', '问题', '结果', '原因', '最终 SQL', 'SQL 条数'];
	const lines = rows.map((r) =>
		[
			r.created,
			r.user_name ?? r.user_id,
			r.question,
			DECISION_LABEL[r.decision],
			r.reason,
			r.sql,
			r.statements.length,
		]
			.map(csvCell)
			.join(','),
	);
	// The BOM makes Excel read the file as UTF-8, so Chinese stays legible.
	const blob = new Blob(['﻿' + [header.map(csvCell).join(','), ...lines].join('\n')], {
		type: 'text/csv;charset=utf-8',
	});
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = `访问审计_${new Date().toISOString().slice(0, 10)}.csv`;
	a.click();
	URL.revokeObjectURL(url);
};

export default function AccessAuditPage() {
	const [rows, setRows] = useState<AccessAuditEntry[]>([]);
	const [count, setCount] = useState(0);
	const [skip, setSkip] = useState(0);
	const [decision, setDecision] = useState<AccessDecision | ''>('');
	const [query, setQuery] = useState('');
	const [search, setSearch] = useState('');
	const [expanded, setExpanded] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		const res = await accessAuditApi.list({
			decision: decision || undefined,
			q: search || undefined,
			skip,
			limit: PAGE_SIZE,
		});
		setLoading(false);
		if (res.error) {
			setError(res.message ?? '加载审计日志失败');
			return;
		}
		setError(null);
		setRows(res.data);
		setCount(res.count);
	}, [decision, search, skip]);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-4">
				<div>
					<h1 className="text-base font-semibold text-heading dark:text-zinc-100">
						访问审计
					</h1>
					<p className="mt-1 text-xs text-secondary dark:text-zinc-400">
						每次问数都会记录提问人、问题、实际执行的全部 SQL，以及数据权限对每条 SQL
						的处理结果（允许 / 改写过滤 / 拦截）。
					</p>
				</div>

				<form
					className="flex flex-wrap items-center gap-2"
					onSubmit={(e) => {
						e.preventDefault();
						setSkip(0);
						setSearch(query.trim());
					}}
				>
					<select
						aria-label="按结果筛选"
						className={INPUT_FILTER}
						value={decision}
						onChange={(e) => {
							setSkip(0);
							setDecision(e.target.value as AccessDecision | '');
						}}
					>
						<option value="">全部结果</option>
						<option value="allowed">允许</option>
						<option value="filtered">已过滤</option>
						<option value="blocked">已拦截</option>
					</select>
					<input
						aria-label="搜索问题或 SQL"
						className={`${INPUT_FILTER} min-w-60 flex-1`}
						placeholder="搜索问题或 SQL…"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
					/>
					<Button type="submit" theme={ButtonTheme.Secondary} size={Size.SMALL}>
						搜索
					</Button>
					<Button
						type="button"
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						disabled={rows.length === 0}
						onClick={() => downloadCsv(rows)}
					>
						导出本页 CSV
					</Button>
				</form>

				{error && (
					<p role="alert" className="text-xs text-red-600 dark:text-red-400">
						{error}
					</p>
				)}

				<div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950/50">
					<table className="w-full min-w-[52rem] text-left text-xs">
						<thead className="bg-zinc-50 text-secondary dark:bg-zinc-900 dark:text-zinc-400">
							<tr>
								<th className="px-3 py-2 font-medium">时间</th>
								<th className="px-3 py-2 font-medium">用户</th>
								<th className="px-3 py-2 font-medium">问题</th>
								<th className="px-3 py-2 font-medium">结果</th>
								<th className="px-3 py-2 font-medium">原因</th>
								<th className="whitespace-nowrap px-3 py-2 font-medium">
									SQL 条数
								</th>
							</tr>
						</thead>
						<tbody>
							{!loading && rows.length === 0 && (
								<tr>
									<td
										colSpan={6}
										className="px-3 py-6 text-center text-secondary"
									>
										暂无审计记录
									</td>
								</tr>
							)}
							{rows.map((r) => (
								<Fragment key={r.id}>
									<tr
										className="cursor-pointer border-t border-zinc-100 align-top hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
										onClick={() => setExpanded(expanded === r.id ? null : r.id)}
										aria-expanded={expanded === r.id}
									>
										<td className="whitespace-nowrap px-3 py-2 text-secondary">
											{r.created
												? formatDate(r.created, 'YYYY-MM-DD HH:mm:ss')
												: '—'}
										</td>
										<td className="whitespace-nowrap px-3 py-2 text-body dark:text-zinc-300">
											{r.user_name ?? r.user_id ?? '—'}
										</td>
										<td className="min-w-64 max-w-md px-3 py-2 text-body dark:text-zinc-300">
											{r.question}
										</td>
										<td className="px-3 py-2">
											<span
												className={`whitespace-nowrap rounded-full px-2 py-0.5 ${DECISION_CLASS[r.decision]}`}
											>
												{DECISION_LABEL[r.decision]}
											</span>
										</td>
										<td className="min-w-48 max-w-xs px-3 py-2 text-secondary">
											{r.reason ?? '—'}
										</td>
										<td className="px-3 py-2 text-secondary">
											{r.statements.length}
										</td>
									</tr>
									{expanded === r.id && (
										<tr className="border-t border-zinc-100 dark:border-zinc-800">
											<td
												colSpan={6}
												className="bg-zinc-50/60 px-3 py-3 dark:bg-zinc-900/60"
											>
												<ol className="flex flex-col gap-2">
													{r.statements.map((st, i) => (
														<li key={i} className="flex flex-col gap-1">
															<span>
																<span
																	className={`mr-2 rounded-full px-2 py-0.5 ${DECISION_CLASS[st.decision]}`}
																>
																	{DECISION_LABEL[st.decision]}
																</span>
																<span className="text-secondary">
																	{st.reason}
																</span>
															</span>
															<pre className="overflow-x-auto whitespace-pre-wrap rounded bg-zinc-900 p-2 text-[11px] text-zinc-100">
																{st.executed_sql ?? st.sql}
															</pre>
															{st.executed_sql &&
																st.executed_sql !== st.sql && (
																	<details className="text-secondary">
																		<summary className="cursor-pointer">
																			改写前的 SQL
																		</summary>
																		<pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded bg-zinc-800 p-2 text-[11px] text-zinc-200">
																			{st.sql}
																		</pre>
																	</details>
																)}
														</li>
													))}
												</ol>
											</td>
										</tr>
									)}
								</Fragment>
							))}
						</tbody>
					</table>
				</div>

				<div className="flex items-center justify-between text-xs text-secondary">
					<span>共 {count} 条</span>
					<div className="flex gap-2">
						<Button
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							disabled={skip === 0}
							onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
						>
							上一页
						</Button>
						<Button
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							disabled={skip + PAGE_SIZE >= count}
							onClick={() => setSkip(skip + PAGE_SIZE)}
						>
							下一页
						</Button>
					</div>
				</div>
			</div>
		</main>
	);
}
