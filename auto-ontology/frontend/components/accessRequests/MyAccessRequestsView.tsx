// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { accessRequestsApi } from '@/api/accessRequests';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { Modal } from '@/common/modal';
import { KIND_LABEL, STATUS_BADGE } from '@/components/accessRequests/labels';
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
	SECTION_TITLE,
} from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type { AccessRequest, AccessRestriction } from '@/types/accessRequests';

/** Whether a blocked field such as ``customers.phone`` names this restriction. */
const matches = (restriction: AccessRestriction, field: string) =>
	restriction.target.toLowerCase().endsWith(field.toLowerCase());

const RequestDialog = ({
	restriction,
	question,
	onClose,
	onSent,
}: {
	restriction: AccessRestriction;
	question: string;
	onClose: () => void;
	onSent: () => void;
}) => {
	const [reason, setReason] = useState('');
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const send = async () => {
		setBusy(true);
		setError(null);
		const res = await accessRequestsApi.create({
			policy_id: restriction.policy_id,
			reason,
			question: question || undefined,
		});
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '提交失败');
			return;
		}
		onSent();
	};

	return (
		<form
			className="flex flex-col gap-3 p-5"
			onSubmit={(e) => {
				e.preventDefault();
				void send();
			}}
		>
			<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">申请访问</h2>
			<p className="text-xs text-body dark:text-zinc-300">
				<code className="font-mono">{restriction.target}</code>
				<span className="ml-2 text-secondary">当前：{restriction.effect}</span>
			</p>
			{question && (
				<p className="rounded-md bg-zinc-50 p-2 text-xs text-secondary dark:bg-zinc-900">
					被拦截的问题：{question}
				</p>
			)}
			<label className={LABEL}>
				申请理由
				<textarea
					className={INPUT}
					rows={3}
					value={reason}
					autoFocus
					placeholder="例如：需要按手机号核对会员回访名单"
					onChange={(e) => setReason(e.target.value)}
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
					disabled={busy || !reason.trim()}
				>
					{busy ? '提交中…' : '提交申请'}
				</Button>
			</div>
		</form>
	);
};

export const MyAccessRequestsView = () => {
	const params = useSearchParams();
	const field = params.get('field') ?? '';
	const question = params.get('question') ?? '';
	const [restrictions, setRestrictions] = useState<AccessRestriction[] | null>(null);
	const [requests, setRequests] = useState<AccessRequest[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);
	const [asking, setAsking] = useState<AccessRestriction | null>(null);
	const opened = useRef(false);

	const load = useCallback(async () => {
		const res = await accessRequestsApi.mine();
		if (res.error) {
			setError(res.message ?? '加载失败');
			return null;
		}
		setError(null);
		setRestrictions(res.restrictions);
		setRequests(res.requests);
		return res.restrictions;
	}, []);

	useEffect(() => {
		void (async () => {
			const loaded = await load();
			// Arriving from a blocked answer opens the request for that field.
			if (!loaded || !field || opened.current) return;
			opened.current = true;
			const hits = loaded.filter((r) => matches(r, field) && !r.pending_request_id);
			if (hits.length === 1) setAsking(hits[0]);
		})();
	}, [load, field]);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full max-w-4xl space-y-5">
				<div>
					<h1 className={PAGE_TITLE}>我的权限申请</h1>
					<p className={PAGE_INTRO}>
						下面列出数据权限策略对你的限制。需要时提交申请，管理员批准后，你在网页端和钉钉、飞书机器人里的下一次提问就会生效。
					</p>
				</div>
				{error && <p className={NOTICE_ERROR}>{error}</p>}
				{notice && (
					<p role="status" className={NOTICE_OK}>
						{notice}
					</p>
				)}

				<section className={CARD}>
					<h2 className={SECTION_TITLE}>对我的限制</h2>
					{restrictions === null ? (
						<p className="mt-3 text-xs text-secondary">加载中…</p>
					) : restrictions.length === 0 ? (
						<p className="mt-3 text-xs text-secondary dark:text-zinc-400">
							没有任何限制，你可以查询所有已接入的数据。
						</p>
					) : (
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{restrictions.map((r) => {
								const highlighted = field && matches(r, field);
								return (
									<li
										key={r.policy_id}
										className={`flex flex-wrap items-center justify-between gap-3 py-2.5 ${
											highlighted
												? '-mx-2 rounded-md bg-[#2563eb]/5 px-2'
												: ''
										}`}
									>
										<div className="min-w-0">
											<p className="text-sm text-heading dark:text-zinc-100">
												<code className="font-mono text-xs">
													{r.target}
												</code>
												<span
													className={`${BADGE} ${BADGE_TONE.blue} ml-2`}
												>
													{KIND_LABEL[r.kind]}
												</span>
											</p>
											<p className="mt-0.5 text-xs text-secondary dark:text-zinc-400">
												{r.effect}
												{r.description ? ` · ${r.description}` : ''}
											</p>
										</div>
										{r.pending_request_id ? (
											<span className={`${BADGE} ${BADGE_TONE.amber}`}>
												已申请，等待审批
											</span>
										) : (
											<Button
												theme={
													highlighted
														? ButtonTheme.Primary
														: ButtonTheme.Secondary
												}
												size={Size.SMALL}
												onClick={() => setAsking(r)}
											>
												申请访问
											</Button>
										)}
									</li>
								);
							})}
						</ul>
					)}
				</section>

				<section className={CARD}>
					<h2 className={SECTION_TITLE}>申请记录</h2>
					{requests.length === 0 ? (
						<p className="mt-3 text-xs text-secondary dark:text-zinc-400">
							还没有提交过申请。
						</p>
					) : (
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{requests.map((q) => (
								<li key={q.id} className="py-2.5 text-xs">
									<div className="flex flex-wrap items-center justify-between gap-2">
										<code className="font-mono text-heading dark:text-zinc-100">
											{q.target ?? '（策略已删除）'}
										</code>
										<span
											className={`${BADGE} ${BADGE_TONE[STATUS_BADGE[q.status].tone]}`}
										>
											{STATUS_BADGE[q.status].label}
										</span>
									</div>
									<p className="mt-1 text-secondary dark:text-zinc-400">
										{q.created && formatDate(q.created, 'YYYY-MM-DD HH:mm')}{' '}
										提交
										{q.reason ? ` · 理由：${q.reason}` : ''}
									</p>
									{q.status !== 'pending' && (
										<p className="mt-1 text-body dark:text-zinc-300">
											{q.status === 'approved'
												? '已开通，现在就可以重新提问。'
												: '未通过。'}
											{q.decision_note
												? `管理员备注：${q.decision_note}`
												: ''}
										</p>
									)}
								</li>
							))}
						</ul>
					)}
				</section>
			</div>
			<Modal
				open={asking !== null}
				onClose={() => setAsking(null)}
				className="w-full max-w-lg"
			>
				{asking && (
					<RequestDialog
						restriction={asking}
						question={question}
						onClose={() => setAsking(null)}
						onSent={() => {
							setNotice(
								`已提交 ${asking.target} 的访问申请，管理员审批后会立即生效。`,
							);
							setAsking(null);
							void load();
						}}
					/>
				)}
			</Modal>
		</main>
	);
};
