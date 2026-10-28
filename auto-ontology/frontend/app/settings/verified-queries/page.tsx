// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import { verifiedQueriesApi } from '@/api/governance';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { Modal } from '@/common/modal';
import { SqlBlock } from '@/common/SqlBlock';
import { ButtonTheme, Size } from '@/enums/button';
import type { VerifiedQuery, VerifiedStatus } from '@/types/governance';
import { INPUT, PAGE_MAIN } from '@/components/settings/pageStyles';

const TABS: { key: VerifiedStatus | ''; label: string }[] = [
	{ key: 'pending', label: '待审核' },
	{ key: 'certified', label: '已认证' },
	{ key: 'rejected', label: '已驳回' },
	{ key: '', label: '全部' },
];

const STATUS_LABEL: Record<VerifiedStatus, string> = {
	pending: '待审核',
	certified: '已认证',
	rejected: '已驳回',
};

const STATUS_CLASS: Record<VerifiedStatus, string> = {
	pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
	certified: 'bg-[#2563eb]/10 text-[#1e40af] dark:bg-[#2563eb]/15 dark:text-[#60a5fa]',
	rejected: 'bg-zinc-100 text-secondary dark:bg-zinc-800 dark:text-zinc-400',
};

type Draft = {
	id?: string;
	question: string;
	sql: string;
	database_name: string;
	note: string;
	certify: boolean;
};

export default function VerifiedQueriesPage() {
	const [tab, setTab] = useState<VerifiedStatus | ''>('pending');
	const [query, setQuery] = useState('');
	const [search, setSearch] = useState('');
	const [rows, setRows] = useState<VerifiedQuery[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [draft, setDraft] = useState<Draft | null>(null);
	const [formError, setFormError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		const res = await verifiedQueriesApi.list({
			status: tab || undefined,
			q: search || undefined,
		});
		setLoading(false);
		if (res.error) {
			setError(res.message ?? '加载问答库失败');
			return;
		}
		setError(null);
		setRows(res.data);
	}, [tab, search]);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const setStatus = async (row: VerifiedQuery, status: VerifiedStatus) => {
		const res = await verifiedQueriesApi.update(row.id, { status });
		if (res.error) setError(res.message ?? '操作失败');
		await load();
	};

	const remove = async (row: VerifiedQuery) => {
		if (!window.confirm('确定删除这条问答吗？')) return;
		const res = await verifiedQueriesApi.remove(row.id);
		if (res.error) setError(res.message ?? '删除失败');
		await load();
	};

	const save = async () => {
		if (!draft || saving) return;
		setSaving(true);
		setFormError(null);
		const input = {
			question: draft.question,
			sql: draft.sql,
			database_name: draft.database_name || null,
			note: draft.note || null,
		};
		const res = draft.id
			? await verifiedQueriesApi.update(draft.id, input)
			: await verifiedQueriesApi.create({
					...input,
					status: draft.certify ? 'certified' : 'pending',
				});
		setSaving(false);
		if (res.error) {
			setFormError(res.message ?? '保存失败');
			return;
		}
		setDraft(null);
		await load();
	};

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-4">
				<div className="flex flex-wrap items-start justify-between gap-3">
					<div>
						<h1 className="text-base font-semibold text-heading dark:text-zinc-100">
							认证问答库
						</h1>
						<p className="mt-1 max-w-3xl text-xs text-secondary dark:text-zinc-400">
							用户在回答下点“有用”或提交修正 SQL
							后进入待审核。认证通过的问答会在之后遇到相似问题时作为示例提供给
							AI，并在“回答依据”中列出，回答会越用越准。
						</p>
					</div>
					<Button
						theme={ButtonTheme.Primary}
						size={Size.SMALL}
						onClick={() => {
							setFormError(null);
							setDraft({
								question: '',
								sql: '',
								database_name: '',
								note: '',
								certify: true,
							});
						}}
					>
						新增问答
					</Button>
				</div>

				<div className="flex flex-wrap items-center gap-2">
					<div
						role="tablist"
						className="flex rounded-lg border border-zinc-200 p-0.5 dark:border-zinc-700"
					>
						{TABS.map((t) => (
							<button
								key={t.key || 'all'}
								type="button"
								role="tab"
								aria-selected={tab === t.key}
								onClick={() => setTab(t.key)}
								className={`rounded-md px-3 py-1 text-xs ${
									tab === t.key
										? 'bg-[#2563eb] text-white'
										: 'text-secondary hover:text-heading dark:text-zinc-400'
								}`}
							>
								{t.label}
							</button>
						))}
					</div>
					<form
						className="flex flex-1 gap-2"
						onSubmit={(e) => {
							e.preventDefault();
							setSearch(query.trim());
						}}
					>
						<input
							aria-label="搜索问题或 SQL"
							className={`${INPUT} py-1.5`}
							placeholder="搜索问题或 SQL…"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
						/>
						<Button type="submit" theme={ButtonTheme.Secondary} size={Size.SMALL}>
							搜索
						</Button>
					</form>
				</div>

				{error && (
					<p role="alert" className="text-xs text-red-600 dark:text-red-400">
						{error}
					</p>
				)}

				{!loading && rows.length === 0 && (
					<p className="rounded-lg border border-dashed border-zinc-300 px-4 py-8 text-center text-xs text-secondary dark:border-zinc-700">
						{tab === 'pending' ? '没有待审核的问答' : '暂无问答'}
					</p>
				)}

				<ul className="flex flex-col gap-3">
					{rows.map((row) => (
						<li
							key={row.id}
							className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950/50"
						>
							<div className="flex flex-wrap items-start justify-between gap-2">
								<p className="text-sm font-medium text-heading dark:text-zinc-100">
									{row.question}
								</p>
								<span
									className={`rounded-full px-2 py-0.5 text-xs ${STATUS_CLASS[row.status]}`}
								>
									{STATUS_LABEL[row.status]}
								</span>
							</div>
							<SqlBlock sql={row.sql} className="mt-2" />
							{row.note && (
								<p className="mt-2 text-xs text-body dark:text-zinc-300">
									说明：{row.note}
								</p>
							)}
							<div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-secondary dark:text-zinc-400">
								<span>
									{row.source === 'feedback' ? '来自回答反馈' : '手动添加'} ·{' '}
									{row.created_by_name ?? '未知'} ·{' '}
									{row.created ? formatDate(row.created, 'YYYY-MM-DD HH:mm') : ''}
									{row.database_name ? ` · 数据库 ${row.database_name}` : ''}
									{row.reviewed_by_name
										? ` · 审核人 ${row.reviewed_by_name}`
										: ''}
									{!row.has_embedding ? ' · 未生成向量，暂不参与检索' : ''}
								</span>
								<span className="flex gap-3 text-xs">
									{row.status !== 'certified' && (
										<button
											type="button"
											className="text-[#2563eb] hover:underline dark:text-[#60a5fa]"
											onClick={() => {
												void setStatus(row, 'certified');
											}}
										>
											认证
										</button>
									)}
									{row.status !== 'rejected' && (
										<button
											type="button"
											className="text-amber-600 hover:underline dark:text-amber-400"
											onClick={() => {
												void setStatus(row, 'rejected');
											}}
										>
											驳回
										</button>
									)}
									<button
										type="button"
										className="text-body hover:underline dark:text-zinc-300"
										onClick={() => {
											setFormError(null);
											setDraft({
												id: row.id,
												question: row.question,
												sql: row.sql,
												database_name: row.database_name ?? '',
												note: row.note ?? '',
												certify: row.status === 'certified',
											});
										}}
									>
										编辑
									</button>
									<button
										type="button"
										className="text-red-600 hover:underline dark:text-red-400"
										onClick={() => {
											void remove(row);
										}}
									>
										删除
									</button>
								</span>
							</div>
						</li>
					))}
				</ul>
			</div>

			<Modal open={draft !== null} onClose={() => setDraft(null)} className="w-full max-w-xl">
				{draft && (
					<form
						className="flex flex-col gap-3 p-5"
						onSubmit={(e) => {
							e.preventDefault();
							void save();
						}}
					>
						<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
							{draft.id ? '编辑问答' : '新增问答'}
						</h2>
						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							问题
							<input
								className={INPUT}
								value={draft.question}
								onChange={(e) => setDraft({ ...draft, question: e.target.value })}
								required
							/>
						</label>
						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							SQL
							<textarea
								className={`${INPUT} font-mono text-xs`}
								rows={8}
								spellCheck={false}
								value={draft.sql}
								onChange={(e) => setDraft({ ...draft, sql: e.target.value })}
								required
							/>
						</label>
						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							数据库（Catalog，可选；留空则对所有数据库生效）
							<input
								className={INPUT}
								value={draft.database_name}
								placeholder="例如：workspace"
								onChange={(e) =>
									setDraft({ ...draft, database_name: e.target.value })
								}
							/>
						</label>
						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							说明（可选）
							<input
								className={INPUT}
								value={draft.note}
								onChange={(e) => setDraft({ ...draft, note: e.target.value })}
							/>
						</label>
						{!draft.id && (
							<label className="flex items-center gap-2 text-sm text-body dark:text-zinc-300">
								<input
									type="checkbox"
									checked={draft.certify}
									onChange={(e) =>
										setDraft({ ...draft, certify: e.target.checked })
									}
								/>
								直接认证（立即参与相似问题检索）
							</label>
						)}
						{formError && (
							<p role="alert" className="text-xs text-red-600 dark:text-red-400">
								{formError}
							</p>
						)}
						<div className="flex justify-end gap-2">
							<Button
								type="button"
								theme={ButtonTheme.Secondary}
								size={Size.SMALL}
								onClick={() => setDraft(null)}
							>
								取消
							</Button>
							<Button
								type="submit"
								theme={ButtonTheme.Primary}
								size={Size.SMALL}
								disabled={saving}
							>
								{saving ? '保存中…' : '保存'}
							</Button>
						</div>
					</form>
				)}
			</Modal>
		</main>
	);
}
