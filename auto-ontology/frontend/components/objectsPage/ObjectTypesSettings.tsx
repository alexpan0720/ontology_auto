// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { objectTypesApi } from '@/api/objects';
import { Button } from '@/common/Button';
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
import type { ObjectLayerSummary, ObjectType } from '@/types/objects';
import { ObjectTypeEditor } from './ObjectTypeEditor';
import { objectHref } from './format';

const TypeRow = ({
	type,
	selected,
	onSelect,
	onEdit,
	onDelete,
}: {
	type: ObjectType;
	selected?: boolean;
	onSelect?: (checked: boolean) => void;
	onEdit: () => void;
	onDelete?: () => void;
}) => (
	<li className="flex items-center gap-3 py-2.5">
		{onSelect && (
			<input
				type="checkbox"
				checked={selected}
				aria-label={`选择 ${type.display_name}`}
				onChange={(e) => onSelect(e.target.checked)}
			/>
		)}
		<div className="min-w-0 flex-1">
			<p className="flex items-center gap-2 text-sm">
				<span className="font-medium text-heading dark:text-zinc-100">
					{type.display_name}
				</span>
				<span className="truncate font-mono text-[11px] text-secondary">
					{type.schema_name}.{type.table_name}
				</span>
			</p>
			<p className="truncate text-xs text-secondary dark:text-zinc-400">
				主键 {type.pk_column}
				{type.title_column ? ` · 标题 ${type.title_column}` : ''}
				{type.status === 'active' ? ` · ${type.link_count} 个关系` : ''}
				{type.description ? ` · ${type.description}` : ''}
			</p>
		</div>
		{type.status === 'active' && (
			<Link
				href={objectHref(type.id)}
				className="text-xs text-secondary hover:text-[#1d4ed8] hover:underline"
			>
				查看
			</Link>
		)}
		<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onEdit}>
			编辑
		</Button>
		{onDelete && (
			<Button theme={ButtonTheme.DangerSubtle} size={Size.SMALL} onClick={onDelete}>
				删除
			</Button>
		)}
	</li>
);

export const ObjectTypesSettings = () => {
	const [types, setTypes] = useState<ObjectType[] | null>(null);
	const [summary, setSummary] = useState<ObjectLayerSummary | null>(null);
	const [selected, setSelected] = useState<Set<string>>(new Set());
	const [editing, setEditing] = useState<string | null>(null);
	const [deleting, setDeleting] = useState<ObjectType | null>(null);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);

	const load = useCallback(async () => {
		const res = await objectTypesApi.list();
		if (res.error) {
			setError(res.message ?? '加载失败');
			return;
		}
		setTypes(res.data);
		setSummary(res.summary);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const candidates = (types ?? []).filter((t) => t.status === 'candidate');
	const active = (types ?? []).filter((t) => t.status === 'active');

	const generate = async () => {
		setBusy(true);
		setError(null);
		setNotice(null);
		const res = await objectTypesApi.generate();
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '生成失败');
			return;
		}
		const keyless = res.keyless_tables.length
			? `；${res.keyless_tables.length} 张表没有可识别的主键，未生成（${res.keyless_tables
					.slice(0, 5)
					.join('、')}${res.keyless_tables.length > 5 ? ' 等' : ''}）`
			: '';
		setNotice(`新增 ${res.types} 个候选对象、${res.links} 个候选关系${keyless}`);
		await load();
	};

	const bulk = async (ids: string[], action: 'accept' | 'delete') => {
		if (ids.length === 0) return;
		setBusy(true);
		setError(null);
		const res = await objectTypesApi.bulk(ids, action);
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '操作失败');
			return;
		}
		setNotice(
			action === 'accept'
				? `已确认 ${res.types} 个对象、${res.links} 个关系`
				: `已忽略 ${res.types} 个候选对象`,
		);
		setSelected(new Set());
		await load();
	};

	const toggle = (id: string, checked: boolean) => {
		const next = new Set(selected);
		if (checked) next.add(id);
		else next.delete(id);
		setSelected(next);
	};

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div className="flex flex-wrap items-start justify-between gap-3">
					<div>
						<h1 className={PAGE_TITLE}>对象类型</h1>
						<p className={PAGE_INTRO}>
							在数据表之上定义业务对象（如客户、订单、商品）以及它们之间的关系。系统根据数据目录中的主键、外键和语义外键生成候选，确认后所有用户可在「对象」页面按对象浏览数据，查询遵循各自的数据权限。
						</p>
					</div>
					<Button
						theme={ButtonTheme.Primary}
						size={Size.SMALL}
						disabled={busy}
						onClick={() => void generate()}
					>
						{busy ? '处理中…' : '从数据目录生成候选'}
					</Button>
				</div>

				{summary && (
					<p className="flex flex-wrap gap-2 text-xs">
						<span className={`${BADGE} ${BADGE_TONE.green}`}>
							已确认 {summary.active_types} 个对象 · {summary.active_links} 个关系
						</span>
						{(summary.candidate_types > 0 || summary.candidate_links > 0) && (
							<span className={`${BADGE} ${BADGE_TONE.amber}`}>
								待确认 {summary.candidate_types} 个对象 · {summary.candidate_links}{' '}
								个关系
							</span>
						)}
					</p>
				)}
				{error && (
					<p role="alert" className={NOTICE_ERROR}>
						{error}
					</p>
				)}
				{notice && <p className={NOTICE_OK}>{notice}</p>}

				{candidates.length > 0 && (
					<section className={CARD}>
						<div className="flex flex-wrap items-center gap-2">
							<h2 className={SECTION_TITLE}>待确认（{candidates.length}）</h2>
							<div className="ml-auto flex gap-2">
								<Button
									theme={ButtonTheme.Secondary}
									size={Size.SMALL}
									disabled={busy || selected.size === 0}
									onClick={() => void bulk([...selected], 'delete')}
								>
									忽略所选
								</Button>
								<Button
									theme={ButtonTheme.Soft}
									size={Size.SMALL}
									disabled={busy || selected.size === 0}
									onClick={() => void bulk([...selected], 'accept')}
								>
									确认所选
								</Button>
								<Button
									theme={ButtonTheme.Primary}
									size={Size.SMALL}
									disabled={busy}
									onClick={() =>
										void bulk(
											candidates.map((t) => t.id),
											'accept',
										)
									}
								>
									全部确认
								</Button>
							</div>
						</div>
						<p className="mt-1 text-[11px] text-secondary">
							确认对象时，它与其他已确认对象之间的候选关系会一并确认。被忽略的表下次生成时会再次出现。
						</p>
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{candidates.map((t) => (
								<TypeRow
									key={t.id}
									type={t}
									selected={selected.has(t.id)}
									onSelect={(checked) => toggle(t.id, checked)}
									onEdit={() => setEditing(t.id)}
								/>
							))}
						</ul>
					</section>
				)}

				<section className={CARD}>
					<h2 className={SECTION_TITLE}>已确认的对象（{active.length}）</h2>
					{types === null ? (
						<p className="mt-2 text-xs text-secondary">加载中…</p>
					) : active.length === 0 ? (
						<p className="mt-2 text-xs text-secondary">
							还没有已确认的对象。点击右上角「从数据目录生成候选」开始。
						</p>
					) : (
						<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
							{active.map((t) => (
								<TypeRow
									key={t.id}
									type={t}
									onEdit={() => setEditing(t.id)}
									onDelete={() => setDeleting(t)}
								/>
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
				{editing && (
					<ObjectTypeEditor
						typeId={editing}
						allTypes={types ?? []}
						onClose={() => setEditing(null)}
						onSaved={() => void load()}
					/>
				)}
			</Modal>
			<ConfirmModal
				open={deleting !== null}
				title="删除对象类型"
				message={
					deleting
						? `删除“${deleting.display_name}”及与它相连的所有关系？数据表本身不受影响。`
						: ''
				}
				confirmLabel="删除"
				tone="danger"
				onCancel={() => setDeleting(null)}
				onConfirm={async () => {
					if (!deleting) return;
					const res = await objectTypesApi.remove(deleting.id);
					setDeleting(null);
					if (res.error) setError(res.message ?? '删除失败');
					await load();
				}}
			/>
		</main>
	);
};
