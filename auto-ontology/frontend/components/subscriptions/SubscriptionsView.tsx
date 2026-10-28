// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import { pushChannelsApi, subscriptionsApi } from '@/api/subscriptions';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { ConfirmModal, Modal } from '@/common/modal';
import {
	BADGE,
	BADGE_TONE,
	CARD,
	NOTICE_ERROR,
	NOTICE_OK,
	PAGE_INTRO,
	PAGE_MAIN,
	PAGE_TITLE,
	SECTION_TITLE,
} from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type {
	PushChannel,
	RunStatus,
	Subscription,
	SubscriptionFields,
	SubscriptionOptions,
	SubscriptionRun,
} from '@/types/subscriptions';
import { ChannelsSection } from './ChannelsSection';
import { EMPTY_FIELDS, SubscriptionEditor, fieldsOf } from './SubscriptionEditor';

const RUN_BADGE: Record<RunStatus, { label: string; tone: keyof typeof BADGE_TONE }> = {
	sent: { label: '已推送', tone: 'green' },
	quiet: { label: '未触发', tone: 'grey' },
	failed: { label: '失败', tone: 'red' },
};

const when = (iso: string | null) => (iso ? formatDate(iso, 'MM-DD HH:mm') : '—');

const RunLine = ({ run }: { run: SubscriptionRun }) => (
	<p className="flex flex-wrap items-center gap-1.5 text-xs text-secondary dark:text-zinc-400">
		<span className={`${BADGE} ${BADGE_TONE[RUN_BADGE[run.status].tone]}`}>
			{RUN_BADGE[run.status].label}
		</span>
		{run.alerted && <span className={`${BADGE} ${BADGE_TONE.red}`}>预警</span>}
		<span>{when(run.created)}</span>
		<span>{run.trigger === 'manual' ? '手动' : '定时'}</span>
		{run.summary && <span className="text-body dark:text-zinc-300">{run.summary}</span>}
	</p>
);

const RunsDialog = ({
	subscription,
	onClose,
}: {
	subscription: Subscription;
	onClose: () => void;
}) => {
	const [runs, setRuns] = useState<SubscriptionRun[] | null>(null);
	useEffect(() => {
		void subscriptionsApi
			.runs(subscription.id)
			.then((res) => setRuns(res.error ? [] : res.data));
	}, [subscription.id]);
	return (
		<div className="flex max-h-[80vh] flex-col p-5">
			<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
				“{subscription.name}”的运行记录
			</h2>
			<div className="mt-3 flex-1 overflow-y-auto">
				{runs === null ? (
					<p className="text-xs text-secondary">加载中…</p>
				) : runs.length === 0 ? (
					<p className="text-xs text-secondary">还没有运行过。</p>
				) : (
					<ul className="space-y-3">
						{runs.map((r) => (
							<li
								key={r.id}
								className="border-b border-zinc-100 pb-2 dark:border-zinc-800"
							>
								<RunLine run={r} />
								{r.deliveries.length > 0 && (
									<p className="mt-1 text-[11px] text-secondary">
										{r.deliveries
											.map((d) => `${d.name}：${d.ok ? '✓' : d.detail}`)
											.join('；')}
									</p>
								)}
								{r.rows && r.rows.length > 0 && (
									<p className="mt-1 truncate text-[11px] text-secondary">
										结果 {r.rows.length} 行，首行：
										{Object.entries(r.rows[0])
											.map(([k, v]) => `${k}=${String(v)}`)
											.join('，')}
									</p>
								)}
							</li>
						))}
					</ul>
				)}
			</div>
			<div className="mt-3 flex justify-end">
				<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onClose}>
					关闭
				</Button>
			</div>
		</div>
	);
};

export const SubscriptionsView = () => {
	const [channels, setChannels] = useState<PushChannel[]>([]);
	const [subs, setSubs] = useState<Subscription[] | null>(null);
	const [options, setOptions] = useState<SubscriptionOptions | null>(null);
	const [editing, setEditing] = useState<{
		id: string | null;
		fields: SubscriptionFields;
	} | null>(null);
	const [history, setHistory] = useState<Subscription | null>(null);
	const [deleting, setDeleting] = useState<Subscription | null>(null);
	const [running, setRunning] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);

	const load = useCallback(async () => {
		const [c, s] = await Promise.all([pushChannelsApi.list(), subscriptionsApi.list()]);
		if (c.error || s.error) {
			setError(c.message ?? s.message ?? '加载失败');
			return;
		}
		setError(null);
		setChannels(c.data);
		setSubs(s.data);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const openEditor = async (sub: Subscription | null) => {
		const res = await subscriptionsApi.options();
		if (res.error) {
			setError(res.message ?? '加载选项失败');
			return;
		}
		setOptions(res);
		setEditing(
			sub
				? { id: sub.id, fields: fieldsOf(sub) }
				: {
						id: null,
						fields: {
							...EMPTY_FIELDS,
							channel_ids: res.channels.length === 1 ? [res.channels[0].id] : [],
							database_name: res.databases.length === 1 ? res.databases[0] : null,
						},
					},
		);
	};

	const runNow = async (sub: Subscription) => {
		setRunning(sub.id);
		setNotice(null);
		const res = await subscriptionsApi.run(sub.id);
		setRunning(null);
		if (res.error) {
			setError(res.message ?? '运行失败');
			return;
		}
		setNotice(
			`“${sub.name}”：${RUN_BADGE[res.status].label}${res.summary ? `，${res.summary}` : ''}`,
		);
		await load();
	};

	const toggle = async (sub: Subscription) => {
		const res = await subscriptionsApi.setEnabled(sub.id, !sub.enabled);
		if (res.error) setError(res.message ?? '操作失败');
		await load();
	};

	const channelName = (id: string) => channels.find((c) => c.id === id)?.name ?? '（已删除）';

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div>
					<h1 className={PAGE_TITLE}>订阅与预警</h1>
					<p className={PAGE_INTRO}>
						把常看的指标按时推送到钉钉、飞书群，例如“工作日早上 9 点推送昨日各渠道
						GMV”；也可以设置阈值或环比变化规则，指标异常时第一时间提醒。查询按所选身份的数据权限执行，并记入访问审计。
					</p>
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

				<ChannelsSection channels={channels} onChanged={load} />

				<section className={CARD}>
					<div className="flex flex-wrap items-center justify-between gap-2">
						<h2 className={SECTION_TITLE}>订阅</h2>
						<Button
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							onClick={() => {
								void openEditor(null);
							}}
						>
							新建订阅
						</Button>
					</div>
					{subs === null ? (
						<p className="mt-3 text-xs text-secondary">加载中…</p>
					) : subs.length === 0 ? (
						<p className="mt-3 text-xs text-secondary dark:text-zinc-400">
							还没有订阅。建议先在“认证问答库”里认证常用指标的
							SQL，再从这里选择它创建订阅。
						</p>
					) : (
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{subs.map((sub) => (
								<li key={sub.id} className="py-3">
									<div className="flex flex-wrap items-start justify-between gap-3">
										<div className="min-w-0 flex-1">
											<p className="text-sm font-medium text-heading dark:text-zinc-100">
												{sub.name}
												{!sub.enabled && (
													<span
														className={`${BADGE} ${BADGE_TONE.grey} ml-2`}
													>
														已暂停
													</span>
												)}
											</p>
											<p className="mt-1 text-xs text-secondary dark:text-zinc-400">
												{sub.schedule_text} · 推送到{' '}
												{sub.channel_ids.map(channelName).join('、') || '—'}
												{sub.alert_type !== 'none' && (
													<>
														{' · '}
														<span className="text-amber-700 dark:text-amber-300">
															预警：{sub.alert_text}
															{sub.push_mode === 'on_alert'
																? '（仅预警时推送）'
																: ''}
														</span>
													</>
												)}
												{sub.enabled &&
													sub.next_run_at &&
													` · 下次 ${when(sub.next_run_at)}`}
											</p>
											{sub.last_run && (
												<div className="mt-1">
													<RunLine run={sub.last_run} />
												</div>
											)}
										</div>
										<div className="flex flex-wrap gap-2">
											<Button
												theme={ButtonTheme.Secondary}
												size={Size.SMALL}
												disabled={running === sub.id}
												onClick={() => {
													void runNow(sub);
												}}
											>
												{running === sub.id ? '运行中…' : '立即推送'}
											</Button>
											<Button
												theme={ButtonTheme.Secondary}
												size={Size.SMALL}
												onClick={() => {
													void openEditor(sub);
												}}
											>
												编辑
											</Button>
											<Button
												theme={ButtonTheme.Secondary}
												size={Size.SMALL}
												onClick={() => setHistory(sub)}
											>
												记录
											</Button>
											<Button
												theme={ButtonTheme.Secondary}
												size={Size.SMALL}
												onClick={() => {
													void toggle(sub);
												}}
											>
												{sub.enabled ? '暂停' : '恢复'}
											</Button>
											<Button
												theme={ButtonTheme.Secondary}
												size={Size.SMALL}
												onClick={() => setDeleting(sub)}
											>
												删除
											</Button>
										</div>
									</div>
								</li>
							))}
						</ul>
					)}
				</section>
			</div>

			<Modal
				open={editing !== null}
				onClose={() => setEditing(null)}
				className="w-full max-w-3xl"
			>
				{editing && options && (
					<SubscriptionEditor
						initial={editing.fields}
						subscriptionId={editing.id}
						options={options}
						onClose={() => setEditing(null)}
						onSaved={(message) => {
							setEditing(null);
							setNotice(message);
							void load();
						}}
					/>
				)}
			</Modal>
			<Modal
				open={history !== null}
				onClose={() => setHistory(null)}
				className="w-full max-w-2xl"
			>
				{history && <RunsDialog subscription={history} onClose={() => setHistory(null)} />}
			</Modal>
			<ConfirmModal
				open={deleting !== null}
				title="删除订阅"
				message={`删除“${deleting?.name ?? ''}”及其运行记录？`}
				onCancel={() => setDeleting(null)}
				onConfirm={async () => {
					if (deleting) await subscriptionsApi.remove(deleting.id);
					setDeleting(null);
					await load();
				}}
			/>
		</main>
	);
};
