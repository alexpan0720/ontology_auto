// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { accessPoliciesApi } from '@/api/governance';
import { Button } from '@/common/Button';
import { Modal } from '@/common/modal';
import { ButtonTheme, Size } from '@/enums/button';
import type {
	AccessPolicy,
	AccessPolicyKind,
	MaskStyle,
	PolicyGroupOption,
	PolicyTableOption,
} from '@/types/governance';
import { CARD_COMPACT, INPUT, PAGE_MAIN } from '@/components/settings/pageStyles';
import { KIND_DESCRIPTION } from '@/components/governance/policyLabels';

/** What each style looks like, so the choice is made by example. */
const MASK_STYLE_LABEL: Record<MaskStyle, string> = {
	phone: '手机号：138****5678',
	email: '邮箱：a***@example.com',
	id_number: '证件号：3301**********1234',
	name: '姓名：张**',
	address: '地址：浙江省杭州市****',
	partial: '通用：保留首尾字符 a***z',
	full: '完全遮盖：******',
};

const tableLabel = (t: { database_name: string; schema_name: string; name: string }) =>
	`${t.database_name}.${t.schema_name}.${t.name}`;

type Draft = {
	id?: string;
	kind: AccessPolicyKind;
	table_id: string;
	column_name: string;
	predicate: string;
	/** '' lets the backend pick a style from the column name. */
	mask_style: MaskStyle | '';
	group_ids: string[];
	description: string;
};

const emptyDraft = (kind: AccessPolicyKind): Draft => ({
	kind,
	table_id: '',
	column_name: '',
	predicate: '',
	mask_style: '',
	group_ids: [],
	description: '',
});

const Toggle = ({
	checked,
	label,
	onChange,
}: {
	checked: boolean;
	label: string;
	onChange: () => void;
}) => (
	<button
		type="button"
		role="switch"
		aria-checked={checked}
		aria-label={label}
		onClick={onChange}
		className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
			checked ? 'bg-[#2563eb]' : 'bg-zinc-300 dark:bg-zinc-600'
		}`}
	>
		<span
			className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
				checked ? 'translate-x-4' : 'translate-x-0.5'
			}`}
		/>
	</button>
);

export default function AccessControlPage() {
	const [policies, setPolicies] = useState<AccessPolicy[]>([]);
	const [tables, setTables] = useState<PolicyTableOption[]>([]);
	const [groups, setGroups] = useState<PolicyGroupOption[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);
	const [draft, setDraft] = useState<Draft | null>(null);
	const [formError, setFormError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	const load = useCallback(async () => {
		const [list, options] = await Promise.all([
			accessPoliciesApi.list(),
			accessPoliciesApi.options(),
		]);
		setLoading(false);
		if (list.error || options.error) {
			setError(list.message ?? options.message ?? '加载数据权限失败');
			return;
		}
		setPolicies(list.data);
		setTables(options.tables);
		setGroups(options.groups);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch
		void load();
	}, [load]);

	const maskPolicies = policies.filter((p) => p.kind === 'mask');
	const columnPolicies = policies.filter((p) => p.kind === 'column');
	const rowPolicies = policies.filter((p) => p.kind === 'row');
	const draftTable = useMemo(
		() => tables.find((t) => t.id === draft?.table_id),
		[tables, draft?.table_id],
	);

	const save = async () => {
		if (!draft || saving) return;
		setSaving(true);
		setFormError(null);
		const payload = {
			kind: draft.kind,
			table_id: draft.table_id,
			column_name: draft.kind !== 'row' ? draft.column_name : null,
			predicate: draft.kind === 'row' ? draft.predicate : null,
			mask_style: draft.kind === 'mask' && draft.mask_style ? draft.mask_style : null,
			group_ids: draft.group_ids,
			description: draft.description || null,
		};
		const res = draft.id
			? await accessPoliciesApi.update(draft.id, {
					column_name: payload.column_name,
					predicate: payload.predicate,
					mask_style: payload.mask_style,
					group_ids: payload.group_ids,
					description: payload.description,
				})
			: await accessPoliciesApi.create(payload);
		setSaving(false);
		if (res.error) {
			setFormError(res.message ?? '保存失败');
			return;
		}
		setDraft(null);
		await load();
	};

	const toggle = async (p: AccessPolicy) => {
		const res = await accessPoliciesApi.update(p.id, { enabled: !p.enabled });
		if (res.error) setError(res.message ?? '更新失败');
		await load();
	};

	const remove = async (p: AccessPolicy) => {
		if (!window.confirm('确定删除这条策略吗？删除后立即对所有用户生效。')) return;
		const res = await accessPoliciesApi.remove(p.id);
		if (res.error) setError(res.message ?? '删除失败');
		await load();
	};

	const restrictPii = async () => {
		setNotice(null);
		const res = await accessPoliciesApi.restrictPii();
		if (res.error) {
			setError(res.message ?? '操作失败');
			return;
		}
		const skipped = res.skipped_keys
			? `另有 ${res.skipped_keys} 个编号/关联键字段（如 customer_id）未脱敏，因为遮掩后多表关联会出错；确需保护可手动新建列权限策略。`
			: '';
		setNotice(
			(res.created
				? `已为 ${res.created} 个带 PII 标签的字段生成脱敏策略，普通用户查询时只能看到遮掩后的值。可按需豁免用户组或调整脱敏方式。`
				: '没有新增脱敏策略：带 PII 标签的字段都已有策略，或尚未检测到敏感字段（可在“敏感信息设置”中开启检测）。') +
				skipped,
		);
		await load();
	};

	const groupNames = (p: AccessPolicy) =>
		p.group_names.length
			? p.group_names.join('、')
			: p.kind === 'row'
				? '所有非管理员'
				: p.kind === 'mask'
					? '无（仅管理员看原值）'
					: '仅管理员';

	const renderRows = (list: AccessPolicy[], kind: AccessPolicyKind) =>
		list.length === 0 ? (
			<p className="py-3 text-xs text-secondary dark:text-zinc-400">
				{kind === 'mask'
					? '还没有脱敏策略。可以点上方的“一键脱敏敏感字段”，为已识别的 PII 字段批量生成。'
					: kind === 'column'
						? '还没有列权限策略。'
						: '还没有行权限策略。'}
			</p>
		) : (
			<div className="overflow-x-auto">
				<table className="w-full min-w-[44rem] text-left text-xs">
					<thead className="text-secondary dark:text-zinc-400">
						<tr className="border-b border-zinc-200 dark:border-zinc-700">
							<th className="py-2 pr-3 font-medium">数据表</th>
							<th className="py-2 pr-3 font-medium">
								{kind === 'row'
									? '过滤条件'
									: kind === 'mask'
										? '脱敏字段'
										: '受限字段'}
							</th>
							<th className="py-2 pr-3 font-medium">
								{kind === 'row'
									? '适用用户组'
									: kind === 'mask'
										? '豁免用户组（看原值）'
										: '可查看的用户组'}
							</th>
							<th className="py-2 pr-3 font-medium">说明</th>
							<th className="py-2 pr-3 font-medium">启用</th>
							<th className="py-2 font-medium">操作</th>
						</tr>
					</thead>
					<tbody>
						{list.map((p) => (
							<tr
								key={p.id}
								className="border-b border-zinc-100 align-top last:border-0 dark:border-zinc-800"
							>
								<td className="py-2 pr-3 text-body dark:text-zinc-300">
									{tableLabel({ ...p, name: p.table_name })}
								</td>
								<td className="py-2 pr-3 font-mono text-body dark:text-zinc-300">
									{kind === 'row' ? p.predicate : p.column_name}
									{kind === 'mask' && p.effective_mask_style && (
										<span className="mt-0.5 block font-sans text-[11px] text-secondary dark:text-zinc-400">
											{MASK_STYLE_LABEL[p.effective_mask_style]}
											{p.mask_style ? '' : '（自动识别）'}
										</span>
									)}
								</td>
								<td className="py-2 pr-3 text-body dark:text-zinc-300">
									{groupNames(p)}
								</td>
								<td className="py-2 pr-3 text-secondary dark:text-zinc-400">
									{p.description ?? '—'}
								</td>
								<td className="py-2 pr-3">
									<Toggle
										checked={p.enabled}
										label={`启用策略 ${p.column_name ?? p.predicate ?? ''}`}
										onChange={() => {
											void toggle(p);
										}}
									/>
								</td>
								<td className="whitespace-nowrap py-2">
									<button
										type="button"
										className="mr-3 text-[#2563eb] hover:underline dark:text-[#60a5fa]"
										onClick={() => {
											setFormError(null);
											setDraft({
												id: p.id,
												kind: p.kind,
												table_id: p.table_id,
												column_name: p.column_name ?? '',
												predicate: p.predicate ?? '',
												mask_style: p.mask_style ?? '',
												group_ids: p.group_ids,
												description: p.description ?? '',
											});
										}}
									>
										编辑
									</button>
									<button
										type="button"
										className="text-red-600 hover:underline dark:text-red-400"
										onClick={() => {
											void remove(p);
										}}
									>
										删除
									</button>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div className="flex flex-wrap items-start justify-between gap-3">
					<div>
						<h1 className="text-base font-semibold text-heading dark:text-zinc-100">
							数据权限
						</h1>
						<p className="mt-1 max-w-3xl text-xs text-secondary dark:text-zinc-400">
							按用户组控制智能问数能读取的字段和数据行。策略在每条 SQL
							执行前强制生效（包括取值探测等内部查询），管理员不受限制。表上一旦有行权限策略，未被任何策略覆盖的普通用户将看不到该表的任何数据。
						</p>
					</div>
					<div className="flex gap-2">
						<Button
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							onClick={() => {
								void restrictPii();
							}}
						>
							一键脱敏敏感字段
						</Button>
						<Button
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							onClick={() => {
								setFormError(null);
								setDraft(emptyDraft('mask'));
							}}
						>
							新建策略
						</Button>
					</div>
				</div>

				{error && (
					<p role="alert" className="text-xs text-red-600 dark:text-red-400">
						{error}
					</p>
				)}
				{notice && (
					<p role="status" className="text-xs text-[#1d4ed8] dark:text-[#60a5fa]">
						{notice}
					</p>
				)}

				{loading ? (
					<p className="text-xs text-secondary">加载中…</p>
				) : (
					<>
						<section className={CARD_COMPACT}>
							<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
								脱敏
							</h2>
							<p className="mb-2 mt-1 text-xs text-secondary dark:text-zinc-400">
								普通用户查询时，这些字段只返回遮掩后的值（如
								138****5678、张**），仍可用于计数和分组，但拿不到原值；豁免的用户组和管理员看原值。
							</p>
							{renderRows(maskPolicies, 'mask')}
						</section>
						<section className={CARD_COMPACT}>
							<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
								列权限
							</h2>
							<p className="mb-2 mt-1 text-xs text-secondary dark:text-zinc-400">
								受限字段只有列出的用户组（和管理员）可以查询；其他用户问数时 AI
								看不到这些字段，直接读取会被拒绝。
							</p>
							{renderRows(columnPolicies, 'column')}
						</section>
						<section className={CARD_COMPACT}>
							<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
								行权限
							</h2>
							<p className="mb-2 mt-1 text-xs text-secondary dark:text-zinc-400">
								适用用户组只能看到满足过滤条件的行；同一张表有多条策略时取并集。查询会在执行前自动改写为只读取允许的行。
							</p>
							{renderRows(rowPolicies, 'row')}
						</section>
					</>
				)}
			</div>

			<Modal open={draft !== null} onClose={() => setDraft(null)} className="w-full max-w-lg">
				{draft && (
					<form
						className="flex flex-col gap-3 p-5"
						onSubmit={(e) => {
							e.preventDefault();
							void save();
						}}
					>
						<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
							{draft.id ? '编辑策略' : '新建策略'}
						</h2>

						{!draft.id && (
							<div className="flex gap-4 text-sm text-body dark:text-zinc-300">
								{(['mask', 'column', 'row'] as const).map((kind) => (
									<label key={kind} className="flex items-center gap-1.5">
										<input
											type="radio"
											name="kind"
											checked={draft.kind === kind}
											onChange={() =>
												setDraft({
													...emptyDraft(kind),
													table_id: draft.table_id,
												})
											}
										/>
										{KIND_DESCRIPTION[kind]}
									</label>
								))}
							</div>
						)}

						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							数据表
							<select
								className={INPUT}
								value={draft.table_id}
								disabled={Boolean(draft.id)}
								onChange={(e) =>
									setDraft({
										...draft,
										table_id: e.target.value,
										column_name: '',
									})
								}
								required
							>
								<option value="">请选择数据表</option>
								{tables.map((t) => (
									<option key={t.id} value={t.id}>
										{tableLabel(t)}
									</option>
								))}
							</select>
						</label>

						{draft.kind !== 'row' ? (
							<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
								{draft.kind === 'mask' ? '脱敏字段' : '受限字段'}
								<select
									className={INPUT}
									value={draft.column_name}
									onChange={(e) =>
										setDraft({ ...draft, column_name: e.target.value })
									}
									required
								>
									<option value="">请选择字段</option>
									{(draftTable?.columns ?? []).map((c) => (
										<option key={c} value={c}>
											{c}
										</option>
									))}
								</select>
							</label>
						) : (
							<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
								过滤条件（SQL 布尔表达式，只能引用这张表的字段）
								<textarea
									className={`${INPUT} font-mono`}
									rows={3}
									value={draft.predicate}
									placeholder="例如：province IN ('浙江', '江苏', '上海')"
									onChange={(e) =>
										setDraft({ ...draft, predicate: e.target.value })
									}
									required
								/>
							</label>
						)}

						{draft.kind === 'mask' && (
							<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
								脱敏方式
								<select
									className={INPUT}
									value={draft.mask_style}
									onChange={(e) =>
										setDraft({
											...draft,
											mask_style: e.target.value as MaskStyle | '',
										})
									}
								>
									<option value="">
										自动识别（按字段名判断手机号、邮箱、姓名等）
									</option>
									{(Object.keys(MASK_STYLE_LABEL) as MaskStyle[]).map((style) => (
										<option key={style} value={style}>
											{MASK_STYLE_LABEL[style]}
										</option>
									))}
								</select>
							</label>
						)}

						<fieldset className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							<legend className="mb-1">
								{draft.kind === 'column'
									? '可查看该字段的用户组（不选则仅管理员可见）'
									: draft.kind === 'mask'
										? '豁免的用户组，看原值（不选则所有非管理员都脱敏）'
										: '适用的用户组（不选则适用于所有非管理员）'}
							</legend>
							{groups.length === 0 ? (
								<span>还没有用户组，可在“设置 → 用户”中创建。</span>
							) : (
								<div className="flex flex-wrap gap-x-4 gap-y-1">
									{groups.map((g) => (
										<label
											key={g.id}
											className="flex items-center gap-1.5 text-sm text-body dark:text-zinc-300"
										>
											<input
												type="checkbox"
												checked={draft.group_ids.includes(g.id)}
												onChange={(e) =>
													setDraft({
														...draft,
														group_ids: e.target.checked
															? [...draft.group_ids, g.id]
															: draft.group_ids.filter(
																	(id) => id !== g.id,
																),
													})
												}
											/>
											{g.name}
										</label>
									))}
								</div>
							)}
						</fieldset>

						<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
							说明（可选）
							<input
								className={INPUT}
								value={draft.description}
								onChange={(e) =>
									setDraft({ ...draft, description: e.target.value })
								}
							/>
						</label>

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
