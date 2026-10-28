// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import { accessRequestsApi } from '@/api/accessRequests';
import { accessPoliciesApi } from '@/api/governance';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
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
import { KIND_LABEL, STATUS_BADGE } from '@/components/accessRequests/labels';
import { ButtonTheme, Size } from '@/enums/button';
import type { AccessRequest } from '@/types/accessRequests';
import type { PolicyGroupOption } from '@/types/governance';

const RequestCard = ({
	request,
	groups,
	onDecided,
}: {
	request: AccessRequest;
	groups: PolicyGroupOption[];
	onDecided: (message: string) => Promise<void>;
}) => {
	const [groupId, setGroupId] = useState('');
	const [note, setNote] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const pending = request.status === 'pending';

	const decide = async (approve: boolean) => {
		setBusy(true);
		setError(null);
		const res = approve
			? await accessRequestsApi.approve(request.id, { group_id: groupId || null, note })
			: await accessRequestsApi.reject(request.id, note);
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '操作失败');
			return;
		}
		await onDecided(
			approve
				? `已批准 ${request.user_name} 访问 ${request.target}，下一次提问即生效。`
				: `已驳回 ${request.user_name} 的申请。`,
		);
	};

	return (
		<li className={CARD}>
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-heading dark:text-zinc-100">
						{request.user_name}
						{request.user_email && (
							<span className="ml-1 text-xs font-normal text-secondary">
								{request.user_email}
							</span>
						)}
					</p>
					<p className="mt-1 text-xs text-body dark:text-zinc-300">
						申请访问{' '}
						<code className="font-mono">{request.target ?? '（策略已删除）'}</code>
						{request.kind && (
							<span className={`${BADGE} ${BADGE_TONE.blue} ml-2`}>
								{KIND_LABEL[request.kind]}
							</span>
						)}
						{request.effect && (
							<span className="ml-2 text-secondary">当前：{request.effect}</span>
						)}
					</p>
				</div>
				<div className="shrink-0 text-right text-[11px] text-secondary">
					<span className={`${BADGE} ${BADGE_TONE[STATUS_BADGE[request.status].tone]}`}>
						{STATUS_BADGE[request.status].label}
					</span>
					<p className="mt-1">
						{request.created && formatDate(request.created, 'YYYY-MM-DD HH:mm')}
					</p>
				</div>
			</div>
			{(request.reason || request.question) && (
				<div className="mt-2 space-y-1 rounded-md bg-zinc-50 p-3 text-xs text-body dark:bg-zinc-900 dark:text-zinc-300">
					{request.reason && (
						<p>
							<span className="text-secondary">理由：</span>
							{request.reason}
						</p>
					)}
					{request.question && (
						<p>
							<span className="text-secondary">被拦截的问题：</span>
							{request.question}
						</p>
					)}
				</div>
			)}
			{pending ? (
				<div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
					<label className={LABEL}>
						授权方式
						<select
							className={INPUT}
							value={groupId}
							onChange={(e) => setGroupId(e.target.value)}
						>
							<option value="">只给此人开通（推荐）</option>
							{groups.map((g) => (
								<option key={g.id} value={g.id}>
									加入用户组：{g.name}
									{request.policy_group_ids.includes(g.id)
										? '（该策略已放行此组）'
										: '（会放行整组）'}
								</option>
							))}
						</select>
					</label>
					<label className={LABEL}>
						备注（申请人可见）
						<input
							className={INPUT}
							value={note}
							placeholder="可选"
							onChange={(e) => setNote(e.target.value)}
						/>
					</label>
					<div className="flex gap-2">
						<Button
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							disabled={busy}
							onClick={() => {
								void decide(false);
							}}
						>
							驳回
						</Button>
						<Button
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							disabled={busy}
							onClick={() => {
								void decide(true);
							}}
						>
							批准
						</Button>
					</div>
					<p className="text-[11px] text-secondary sm:col-span-3 dark:text-zinc-500">
						推荐方式会把申请人加入“授权·{request.target}
						”用户组（首次自动创建），只对此人生效；选择已有用户组会放行整组成员。
					</p>
				</div>
			) : (
				<p className="mt-2 text-xs text-secondary dark:text-zinc-400">
					{request.decided_by_name ?? '管理员'} 于{' '}
					{request.decided && formatDate(request.decided, 'YYYY-MM-DD HH:mm')}{' '}
					{request.status === 'approved'
						? `批准${request.granted_group_name ? `，加入用户组“${request.granted_group_name}”` : ''}`
						: '驳回'}
					{request.decision_note ? `：${request.decision_note}` : ''}
				</p>
			)}
			{error && <p className={`${NOTICE_ERROR} mt-2`}>{error}</p>}
		</li>
	);
};

export default function AccessRequestsPage() {
	const [tab, setTab] = useState<'pending' | 'done'>('pending');
	const [requests, setRequests] = useState<AccessRequest[] | null>(null);
	const [pendingCount, setPendingCount] = useState(0);
	const [groups, setGroups] = useState<PolicyGroupOption[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);

	const load = useCallback(async () => {
		const [res, options] = await Promise.all([
			accessRequestsApi.list({}),
			accessPoliciesApi.options(),
		]);
		if (res.error) {
			setError(res.message ?? '加载失败');
			return;
		}
		setError(null);
		setRequests(res.data);
		setPendingCount(res.pending);
		if (!options.error) setGroups(options.groups);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const shown = (requests ?? []).filter((r) =>
		tab === 'pending' ? r.status === 'pending' : r.status !== 'pending',
	);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div>
					<h1 className={PAGE_TITLE}>权限申请</h1>
					<p className={PAGE_INTRO}>
						用户在问数被拦截或只能看到脱敏值时，可以在“我的权限申请”中提交申请。批准会把申请人加入能访问该数据的用户组，只对此人生效，不会放宽策略本身；审批结果记录在这里，申请人也能看到。
					</p>
				</div>
				{error && <p className={NOTICE_ERROR}>{error}</p>}
				{notice && (
					<p role="status" className={NOTICE_OK}>
						{notice}
					</p>
				)}
				<div className="flex gap-2" role="tablist">
					{(
						[
							['pending', `待审批 ${pendingCount}`],
							['done', '已处理'],
						] as const
					).map(([key, label]) => (
						<button
							key={key}
							type="button"
							role="tab"
							aria-selected={tab === key}
							onClick={() => setTab(key)}
							className={`rounded-full px-3 py-1 text-xs ${
								tab === key
									? 'bg-[#2563eb] text-white'
									: 'bg-zinc-100 text-body hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300'
							}`}
						>
							{label}
						</button>
					))}
				</div>
				{requests === null ? (
					<p className="text-xs text-secondary">加载中…</p>
				) : shown.length === 0 ? (
					<p className="text-xs text-secondary dark:text-zinc-400">
						{tab === 'pending' ? '没有待审批的申请。' : '还没有处理过的申请。'}
					</p>
				) : (
					<ul className="space-y-3">
						{shown.map((r) => (
							<RequestCard
								key={r.id}
								request={r}
								groups={groups}
								onDecided={async (message) => {
									setNotice(message);
									await load();
								}}
							/>
						))}
					</ul>
				)}
			</div>
		</main>
	);
}
