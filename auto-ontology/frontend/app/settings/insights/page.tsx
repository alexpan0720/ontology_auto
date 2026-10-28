// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { verifiedQueriesApi } from '@/api/governance';
import { insightsApi } from '@/api/insights';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { Modal } from '@/common/modal';
import {
	BADGE,
	BADGE_TONE,
	CARD,
	INPUT,
	LABEL,
	NOTICE_ERROR,
	NOTICE_OK,
	PAGE_INTRO,
	PAGE_MAIN,
	PAGE_TITLE,
} from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type { InsightBoard, InsightCategory, InsightGroup } from '@/types/insights';

const CATEGORY: Record<
	InsightCategory,
	{ label: string; tone: keyof typeof BADGE_TONE; hint: string }
> = {
	downvoted: { label: '差评', tone: 'red', hint: '提问人点了“没帮助”' },
	error: { label: '报错', tone: 'red', hint: '查询执行失败或服务出错' },
	no_sql: { label: '无法生成查询', tone: 'amber', hint: '语义层里找不到对应的表、指标或术语' },
	empty: { label: '查无数据', tone: 'amber', hint: '查询成功但没有返回任何行' },
	blocked: { label: '权限拦截', tone: 'grey', hint: '提问人没有相关字段或数据行的权限' },
};
const CATEGORY_ORDER: InsightCategory[] = ['downvoted', 'error', 'no_sql', 'empty', 'blocked'];

const SOURCE: Record<string, string> = {
	app: '网页',
	api: 'API',
	dingtalk: '钉钉',
	feishu: '飞书',
};

const ADVICE: Record<InsightCategory, string> = {
	downvoted: '把正确的 SQL 补充到认证问答库，之后相似问题会直接参考它。',
	error: '查看 SQL 和报错，修正后补充到认证问答库。',
	no_sql: '在语义输入中补充相关术语或指标，或直接补充一条认证问答。',
	empty: '确认筛选条件和数据范围；若口径不对，补充一条认证问答。',
	blocked: '如确需开放，请在“权限申请”中审批，或调整数据权限策略。',
};

const Tile = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
	<div className={`${CARD} !p-4`} title={hint}>
		<p className="text-xs text-secondary dark:text-zinc-400">{label}</p>
		<p className="mt-1 text-xl font-semibold text-heading tabular-nums dark:text-zinc-100">
			{value}
		</p>
	</div>
);

const VerifyDialog = ({
	group,
	onClose,
	onSaved,
}: {
	group: InsightGroup;
	onClose: () => void;
	onSaved: () => void;
}) => {
	const [question, setQuestion] = useState(group.question);
	const [sql, setSql] = useState(group.sql ?? '');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const save = async () => {
		setBusy(true);
		setError(null);
		const res = await verifiedQueriesApi.create({ question, sql, status: 'certified' });
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '保存失败');
			return;
		}
		onSaved();
	};

	return (
		<form
			className="flex flex-col gap-3 p-5"
			onSubmit={(e) => {
				e.preventDefault();
				void save();
			}}
		>
			<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">补充认证问答</h2>
			<p className="text-xs text-secondary dark:text-zinc-400">
				保存后立即生效：之后有人问相似的问题，会直接参考这条经过认证的 SQL。
			</p>
			<label className={LABEL}>
				问题
				<input
					className={INPUT}
					value={question}
					onChange={(e) => setQuestion(e.target.value)}
				/>
			</label>
			<label className={LABEL}>
				正确的 SQL
				<textarea
					className={`${INPUT} font-mono text-xs`}
					rows={8}
					value={sql}
					placeholder="SELECT …"
					onChange={(e) => setSql(e.target.value)}
				/>
			</label>
			{error && <p className={NOTICE_ERROR}>{error}</p>}
			<div className="flex justify-end gap-2">
				<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onClose}>
					取消
				</Button>
				<Button
					theme={ButtonTheme.Primary}
					size={Size.SMALL}
					type="submit"
					disabled={busy || !question.trim() || !sql.trim()}
				>
					{busy ? '保存中…' : '保存并认证'}
				</Button>
			</div>
		</form>
	);
};

const GroupRow = ({
	group,
	onVerify,
	onDismiss,
}: {
	group: InsightGroup;
	onVerify: () => void;
	onDismiss: () => void;
}) => {
	const [open, setOpen] = useState(false);
	const categories = CATEGORY_ORDER.filter((c) => group.categories[c]);
	return (
		<li className="py-3">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<button
					type="button"
					className="min-w-0 flex-1 text-left"
					aria-expanded={open}
					onClick={() => setOpen(!open)}
				>
					<p className="text-sm font-medium text-heading dark:text-zinc-100">
						{group.question}
					</p>
					<p className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-secondary dark:text-zinc-400">
						{categories.map((c) => (
							<span
								key={c}
								className={`${BADGE} ${BADGE_TONE[CATEGORY[c].tone]}`}
								title={CATEGORY[c].hint}
							>
								{CATEGORY[c].label}
								{group.categories[c]! > 1 ? ` ×${group.categories[c]}` : ''}
							</span>
						))}
						<span>
							{group.count} 次 · {group.users} 人 ·{' '}
							{group.sources.map((x) => SOURCE[x] ?? x).join('、')} · 最近{' '}
							{formatDate(group.last_seen, 'MM-DD HH:mm')}
						</span>
					</p>
				</button>
				<div className="flex shrink-0 gap-2">
					{group.category === 'blocked' ? (
						<Link
							href="/settings/access-requests"
							className="rounded-md px-2 py-1 text-xs text-[#2563eb] hover:bg-[#2563eb]/10 dark:text-[#60a5fa]"
						>
							查看权限申请
						</Link>
					) : (
						<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onVerify}>
							补充认证问答
						</Button>
					)}
					<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onDismiss}>
						标记已处理
					</Button>
				</div>
			</div>
			{open && (
				<div className="mt-2 space-y-2 rounded-md bg-zinc-50 p-3 text-xs text-body dark:bg-zinc-900 dark:text-zinc-300">
					<p>
						<span className="text-secondary">建议：</span>
						{ADVICE[group.category]}
					</p>
					{group.feedback_note && (
						<p>
							<span className="text-secondary">提问人反馈：</span>
							{group.feedback_note}
						</p>
					)}
					{group.detail && (
						<p className="break-words">
							<span className="text-secondary">系统回复：</span>
							{group.detail}
						</p>
					)}
					{group.sql && (
						<pre className="overflow-x-auto rounded bg-white p-2 font-mono text-[11px] dark:bg-zinc-950">
							{group.sql}
						</pre>
					)}
				</div>
			)}
		</li>
	);
};

export default function InsightsPage() {
	const [days, setDays] = useState(30);
	const [board, setBoard] = useState<InsightBoard | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);
	const [filter, setFilter] = useState<InsightCategory | 'all'>('all');
	const [verifying, setVerifying] = useState<InsightGroup | null>(null);

	const load = useCallback(async () => {
		const res = await insightsApi.board(days);
		if (res.error) {
			setError(res.message ?? '加载失败');
			return;
		}
		setError(null);
		setBoard(res);
	}, [days]);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const groups = useMemo(
		() => (board?.groups ?? []).filter((g) => filter === 'all' || g.categories[filter]),
		[board, filter],
	);

	const dismiss = async (group: InsightGroup, quiet = false) => {
		const res = await insightsApi.dismiss(group.key);
		if (res.error) {
			setError(res.message ?? '操作失败');
			return;
		}
		if (!quiet)
			setNotice(`已标记“${group.question}”为已处理；如果之后再次失败，它会重新出现。`);
		await load();
	};

	const t = board?.totals;
	const pct = (n: number | null | undefined) =>
		n == null ? '—' : `${Math.round(n * 1000) / 10}%`;

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div className="flex flex-wrap items-end justify-between gap-3">
					<div>
						<h1 className={PAGE_TITLE}>问数质量</h1>
						<p className={PAGE_INTRO}>
							汇总网页端和钉钉、飞书机器人里没答好的问题：差评、报错、无法生成查询、查无数据和权限拦截。同一个问题的不同问法会合并在一起，按出现次数排序，方便你优先补充术语、指标或认证问答。
						</p>
					</div>
					<label className="flex items-center gap-2 text-xs text-secondary">
						时间范围
						<select
							className={`${INPUT} !w-auto !py-1`}
							value={days}
							onChange={(e) => setDays(Number(e.target.value))}
						>
							<option value={7}>近 7 天</option>
							<option value={30}>近 30 天</option>
							<option value={90}>近 90 天</option>
						</select>
					</label>
				</div>

				{error && (
					<p role="alert" className={NOTICE_ERROR}>
						{error}
					</p>
				)}
				{notice && (
					<p role="status" className={NOTICE_OK}>
						{notice}
					</p>
				)}

				{t && (
					<div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
						<Tile label="提问" value={t.questions.toLocaleString()} />
						<Tile
							label="成功回答率"
							value={pct(t.answer_rate)}
							hint="返回了数据的提问占比"
						/>
						<Tile label="差评" value={t.downvoted.toLocaleString()} />
						<Tile
							label="报错 / 无法生成"
							value={(t.error + t.no_sql).toLocaleString()}
						/>
						<Tile label="查无数据" value={t.empty.toLocaleString()} />
						<Tile label="权限拦截" value={t.blocked.toLocaleString()} />
					</div>
				)}

				<section className={CARD}>
					<div
						className="flex flex-wrap gap-2"
						role="tablist"
						aria-label="按问题类型筛选"
					>
						{(['all', ...CATEGORY_ORDER] as const).map((c) => {
							const count =
								c === 'all'
									? (board?.groups.length ?? 0)
									: (board?.groups.filter((g) => g.categories[c]).length ?? 0);
							const active = filter === c;
							return (
								<button
									key={c}
									type="button"
									role="tab"
									aria-selected={active}
									onClick={() => setFilter(c)}
									className={`rounded-full px-3 py-1 text-xs transition-colors ${
										active
											? 'bg-[#2563eb] text-white'
											: 'bg-zinc-100 text-body hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300'
									}`}
								>
									{c === 'all' ? '全部' : CATEGORY[c].label} {count}
								</button>
							);
						})}
					</div>
					{board === null ? (
						<p className="mt-4 text-xs text-secondary">加载中…</p>
					) : groups.length === 0 ? (
						<p className="mt-4 text-xs text-secondary dark:text-zinc-400">
							{board.totals.questions === 0
								? `近 ${days} 天还没有提问记录。用户在网页端或机器人里提问后，这里会自动统计。`
								: `近 ${days} 天没有需要处理的问题，做得好！`}
						</p>
					) : (
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{groups.map((g) => (
								<GroupRow
									key={g.key}
									group={g}
									onVerify={() => setVerifying(g)}
									onDismiss={() => {
										void dismiss(g);
									}}
								/>
							))}
						</ul>
					)}
				</section>
			</div>
			<Modal
				open={verifying !== null}
				onClose={() => setVerifying(null)}
				className="w-full max-w-2xl"
			>
				{verifying && (
					<VerifyDialog
						group={verifying}
						onClose={() => setVerifying(null)}
						onSaved={() => {
							setNotice('已加入认证问答库，之后相似的问题会直接参考这条 SQL。');
							const g = verifying;
							setVerifying(null);
							void dismiss(g, true);
						}}
					/>
				)}
			</Modal>
		</main>
	);
}
