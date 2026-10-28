// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useRef, useState } from 'react';
import { subscriptionsApi } from '@/api/subscriptions';
import { Button } from '@/common/Button';
import { INPUT, LABEL, NOTICE_ERROR, SECTION_TITLE } from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type {
	Subscription,
	SubscriptionFields,
	SubscriptionOptions,
	SubscriptionPreview,
} from '@/types/subscriptions';
import { PLATFORM_NAME } from './ChannelsSection';

export const EMPTY_FIELDS: SubscriptionFields = {
	name: '',
	sql: '',
	database_name: null,
	verified_query_id: null,
	schedule: 'workdays',
	time_of_day: '09:00',
	weekday: 1,
	timezone: 'Asia/Shanghai',
	channel_ids: [],
	run_as_user_id: null,
	push_mode: 'always',
	alert_type: 'none',
	alert_column: null,
	alert_op: null,
	alert_value: null,
	enabled: true,
};

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

export const fieldsOf = (s: Subscription): SubscriptionFields => ({
	name: s.name,
	sql: s.sql,
	database_name: s.database_name,
	verified_query_id: s.verified_query_id,
	schedule: s.schedule,
	time_of_day: s.time_of_day,
	weekday: s.weekday ?? 1,
	timezone: s.timezone,
	channel_ids: s.channel_ids,
	run_as_user_id: s.run_as_user_id,
	push_mode: s.push_mode,
	alert_type: s.alert_type,
	alert_column: s.alert_column,
	alert_op: s.alert_op,
	alert_value: s.alert_value,
	enabled: s.enabled,
});

const Fieldset = ({ title, children }: { title: string; children: React.ReactNode }) => (
	<fieldset className="space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
		<legend className={`${SECTION_TITLE} px-1`}>{title}</legend>
		{children}
	</fieldset>
);

const PreviewPanel = ({ preview }: { preview: SubscriptionPreview }) => (
	<div className="space-y-2 rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
		<p className="text-secondary">
			查询返回 {preview.row_count} 行
			{preview.alert.value_column ? `，预警按“${preview.alert.value_column}”列判断` : ''}
		</p>
		{preview.alert.triggered ? (
			<div className="rounded-md bg-red-50 p-2 text-red-700 dark:bg-red-500/10 dark:text-red-300">
				<p className="font-medium">按当前数据会触发预警：</p>
				<ul className="mt-1 list-disc pl-5">
					{preview.alert.lines.map((l) => (
						<li key={l}>{l}</li>
					))}
				</ul>
			</div>
		) : (
			preview.alert.note && (
				<p className="text-amber-700 dark:text-amber-300">{preview.alert.note}</p>
			)
		)}
		{preview.rows.length > 0 && (
			<div className="max-h-48 overflow-auto rounded border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950">
				<table className="w-full text-left text-[11px]">
					<thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-800">
						<tr>
							{preview.columns.map((c) => (
								<th key={c} className="px-2 py-1 font-medium">
									{c}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						{preview.rows.slice(0, 10).map((row, i) => (
							<tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
								{preview.columns.map((c) => (
									<td key={c} className="px-2 py-1 tabular-nums">
										{row[c] === null || row[c] === undefined
											? '—'
											: String(row[c])}
									</td>
								))}
							</tr>
						))}
					</tbody>
				</table>
			</div>
		)}
		<details>
			<summary className="cursor-pointer text-secondary">推送消息预览</summary>
			<pre className="mt-1 whitespace-pre-wrap font-sans text-body dark:text-zinc-300">
				{preview.message.title}
				{'\n\n'}
				{preview.message.body.replace(/<[^>]+>/g, '')}
			</pre>
		</details>
	</div>
);

export const SubscriptionEditor = ({
	initial,
	subscriptionId,
	options,
	onClose,
	onSaved,
}: {
	initial: SubscriptionFields;
	subscriptionId: string | null;
	options: SubscriptionOptions;
	onClose: () => void;
	onSaved: (message: string) => void;
}) => {
	const [f, setF] = useState<SubscriptionFields>(initial);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [preview, setPreview] = useState<SubscriptionPreview | null>(null);
	// The result lands below the form; bring it (or the error) into view.
	const resultRef = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (preview || error)
			resultRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
	}, [preview, error]);
	const set = (changes: Partial<SubscriptionFields>) => {
		setF((prev) => ({ ...prev, ...changes }));
	};

	const pickQuery = (id: string) => {
		const q = options.verified_queries.find((x) => x.id === id);
		if (!q) {
			set({ verified_query_id: null });
			return;
		}
		set({
			verified_query_id: q.id,
			sql: q.sql,
			database_name: q.database_name ?? f.database_name,
			name: f.name || q.question,
		});
		setPreview(null);
	};

	const runPreview = async () => {
		setBusy(true);
		setError(null);
		const res = await subscriptionsApi.preview({
			...f,
			subscription_id: subscriptionId ?? undefined,
		});
		setBusy(false);
		if (res.error) {
			setPreview(null);
			setError(res.message ?? '试运行失败');
			return;
		}
		setPreview(res);
	};

	const save = async () => {
		setBusy(true);
		setError(null);
		const res = subscriptionId
			? await subscriptionsApi.update(subscriptionId, f)
			: await subscriptionsApi.create(f);
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '保存失败');
			return;
		}
		onSaved(subscriptionId ? `已更新“${f.name}”。` : `已创建“${f.name}”，会按计划自动推送。`);
	};

	const columns = preview?.columns ?? [];

	return (
		<form
			className="flex max-h-[85vh] flex-col"
			onSubmit={(e) => {
				e.preventDefault();
				void save();
			}}
		>
			<h2 className="border-b border-zinc-200 px-5 py-3 text-sm font-semibold text-heading dark:border-zinc-700 dark:text-zinc-100">
				{subscriptionId ? '编辑订阅' : '新建订阅'}
			</h2>
			<div className="flex-1 space-y-4 overflow-y-auto p-5">
				<Fieldset title="推送什么">
					<label className={LABEL}>
						从认证问答库选择（推荐，口径经过认证）
						<select
							className={INPUT}
							value={f.verified_query_id ?? ''}
							onChange={(e) => pickQuery(e.target.value)}
						>
							<option value="">自定义 SQL</option>
							{options.verified_queries.map((q) => (
								<option key={q.id} value={q.id}>
									{q.question}
								</option>
							))}
						</select>
					</label>
					<label className={LABEL}>
						名称
						<input
							className={INPUT}
							value={f.name}
							placeholder="例如：昨日各渠道订单"
							onChange={(e) => set({ name: e.target.value })}
						/>
					</label>
					<label className={LABEL}>
						查询 SQL（只允许 SELECT）
						<textarea
							className={`${INPUT} font-mono text-xs`}
							rows={5}
							value={f.sql}
							onChange={(e) => {
								set({ sql: e.target.value, verified_query_id: null });
								setPreview(null);
							}}
						/>
					</label>
					{options.databases.length > 1 && (
						<label className={LABEL}>
							数据库
							<select
								className={INPUT}
								value={f.database_name ?? ''}
								onChange={(e) => set({ database_name: e.target.value || null })}
							>
								<option value="">请选择</option>
								{options.databases.map((d) => (
									<option key={d} value={d}>
										{d}
									</option>
								))}
							</select>
						</label>
					)}
					<label className={LABEL}>
						以谁的数据权限查询
						<select
							className={INPUT}
							value={f.run_as_user_id ?? ''}
							onChange={(e) => set({ run_as_user_id: e.target.value || null })}
						>
							<option value="">
								普通用户，不属于任何用户组（推荐：群里每个人都能看）
							</option>
							{options.users.map((u) => (
								<option key={u.id} value={u.id}>
									{u.name ?? u.email ?? u.id}
									{u.email ? `（${u.email}）` : ''}
								</option>
							))}
						</select>
					</label>
				</Fieldset>

				<Fieldset title="什么时候推送">
					<div className="grid gap-3 sm:grid-cols-3">
						<label className={LABEL}>
							频率
							<select
								className={INPUT}
								value={f.schedule}
								onChange={(e) =>
									set({
										schedule: e.target.value as SubscriptionFields['schedule'],
									})
								}
							>
								<option value="workdays">工作日</option>
								<option value="daily">每天</option>
								<option value="weekly">每周</option>
								<option value="hourly">每小时</option>
							</select>
						</label>
						{f.schedule === 'weekly' && (
							<label className={LABEL}>
								星期
								<select
									className={INPUT}
									value={f.weekday ?? 1}
									onChange={(e) => set({ weekday: Number(e.target.value) })}
								>
									{WEEKDAYS.map((d, i) => (
										<option key={d} value={i + 1}>
											星期{d}
										</option>
									))}
								</select>
							</label>
						)}
						<label className={LABEL}>
							{f.schedule === 'hourly'
								? '每小时的第几分（取分钟）'
								: '时间（北京时间）'}
							<input
								className={INPUT}
								type="time"
								value={f.time_of_day}
								onChange={(e) => set({ time_of_day: e.target.value })}
							/>
						</label>
					</div>
					<div className={LABEL}>
						推送到
						{options.channels.length === 0 ? (
							<p className="text-amber-700 dark:text-amber-300">
								还没有推送渠道，请先关闭此窗口，在“推送渠道”中添加群机器人。
							</p>
						) : (
							<div className="flex flex-wrap gap-3">
								{options.channels.map((c) => (
									<label
										key={c.id}
										className="flex items-center gap-1.5 text-sm text-body dark:text-zinc-300"
									>
										<input
											type="checkbox"
											checked={f.channel_ids.includes(c.id)}
											onChange={(e) =>
												set({
													channel_ids: e.target.checked
														? [...f.channel_ids, c.id]
														: f.channel_ids.filter((x) => x !== c.id),
												})
											}
										/>
										{PLATFORM_NAME[c.platform]} · {c.name}
									</label>
								))}
							</div>
						)}
					</div>
				</Fieldset>

				<Fieldset title="异常预警（可选）">
					<div
						className="flex flex-wrap gap-4 text-sm text-body dark:text-zinc-300"
						role="radiogroup"
					>
						{(
							[
								['none', '不预警，按时推送结果'],
								['threshold', '超过阈值时预警'],
								['change', '较上次变化过大时预警'],
							] as const
						).map(([value, label]) => (
							<label key={value} className="flex items-center gap-1.5">
								<input
									type="radio"
									name="alert_type"
									checked={f.alert_type === value}
									onChange={() =>
										set({
											alert_type: value,
											alert_op:
												value === 'threshold'
													? '<'
													: value === 'change'
														? 'down'
														: null,
											alert_value:
												value === 'none'
													? null
													: (f.alert_value ??
														(value === 'change' ? 20 : null)),
										})
									}
								/>
								{label}
							</label>
						))}
					</div>
					{f.alert_type !== 'none' && (
						<>
							<div className="grid gap-3 sm:grid-cols-3">
								<label className={LABEL}>
									判断哪一列
									<input
										className={INPUT}
										list="alert-columns"
										value={f.alert_column ?? ''}
										placeholder="留空则取第一个数值列"
										onChange={(e) =>
											set({ alert_column: e.target.value || null })
										}
									/>
									<datalist id="alert-columns">
										{columns.map((c) => (
											<option key={c} value={c} />
										))}
									</datalist>
								</label>
								<label className={LABEL}>
									{f.alert_type === 'threshold' ? '条件' : '方向'}
									<select
										className={INPUT}
										value={f.alert_op ?? ''}
										onChange={(e) => set({ alert_op: e.target.value })}
									>
										{f.alert_type === 'threshold' ? (
											<>
												<option value="<">低于</option>
												<option value="<=">不高于</option>
												<option value=">">高于</option>
												<option value=">=">不低于</option>
											</>
										) : (
											<>
												<option value="down">下降</option>
												<option value="up">上涨</option>
												<option value="any">涨跌都算</option>
											</>
										)}
									</select>
								</label>
								<label className={LABEL}>
									{f.alert_type === 'threshold' ? '阈值' : '幅度（%）'}
									<input
										className={INPUT}
										type="number"
										step="any"
										value={f.alert_value ?? ''}
										onChange={(e) =>
											set({
												alert_value:
													e.target.value === ''
														? null
														: Number(e.target.value),
											})
										}
									/>
								</label>
							</div>
							<p className="text-[11px] text-secondary">
								结果有多行时逐行判断（以第一列作为名称，例如按渠道分别预警）；变化预警与上一次成功运行的结果比较。
							</p>
							<label className="flex items-center gap-2 text-sm text-body dark:text-zinc-300">
								<input
									type="checkbox"
									checked={f.push_mode === 'on_alert'}
									onChange={(e) =>
										set({ push_mode: e.target.checked ? 'on_alert' : 'always' })
									}
								/>
								只在触发预警时推送（不打扰群里的人）
							</label>
						</>
					)}
				</Fieldset>

				<div ref={resultRef} className="space-y-2">
					{preview && <PreviewPanel preview={preview} />}
					{error && (
						<p role="alert" className={NOTICE_ERROR}>
							{error}
						</p>
					)}
				</div>
			</div>
			<div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-700">
				<Button
					theme={ButtonTheme.Secondary}
					size={Size.SMALL}
					disabled={busy || !f.sql.trim()}
					onClick={() => {
						void runPreview();
					}}
				>
					{busy ? '运行中…' : '试运行（不推送）'}
				</Button>
				<div className="flex gap-2">
					<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onClose}>
						取消
					</Button>
					<Button
						theme={ButtonTheme.Primary}
						size={Size.SMALL}
						type="submit"
						disabled={busy || !f.name.trim() || !f.sql.trim()}
					>
						保存
					</Button>
				</div>
			</div>
		</form>
	);
};
