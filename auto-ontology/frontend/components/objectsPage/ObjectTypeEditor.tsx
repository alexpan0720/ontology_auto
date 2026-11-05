// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import { linkTypesApi, objectTypesApi } from '@/api/objects';
import { Button } from '@/common/Button';
import {
	BADGE,
	BADGE_TONE,
	INPUT,
	INPUT_DENSE,
	LABEL,
	NOTICE_ERROR,
	SECTION_TITLE,
} from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type { LinkType, ObjectType, ObjectTypeDetail } from '@/types/objects';

const ORIGIN_LABEL: Record<LinkType['origin'], string> = {
	foreign_key: '外键',
	semantic_fk: '语义外键',
	manual: '手动',
};

type PropertyDraft = { column_name: string; display_name: string; hidden: boolean };

const LinkRow = ({
	link,
	typeId,
	onChanged,
	onError,
}: {
	link: LinkType;
	typeId: string;
	onChanged: () => void;
	onError: (message: string) => void;
}) => {
	const [forward, setForward] = useState(link.display_name);
	const [reverse, setReverse] = useState(link.reverse_display_name);
	const outgoing = link.object_type_id === typeId;
	const dirty = forward !== link.display_name || reverse !== link.reverse_display_name;

	const act = async (call: Promise<{ error?: boolean; message?: string }>) => {
		const res = await call;
		if (res.error) onError(res.message ?? '操作失败');
		onChanged();
	};

	return (
		<li className="space-y-1.5 py-2.5">
			<p className="flex flex-wrap items-center gap-1.5 text-xs text-secondary">
				<span className="font-medium text-heading dark:text-zinc-100">
					{link.source_type?.display_name ?? '?'}
				</span>
				<span className="font-mono">.{link.source_column}</span>
				<span>→</span>
				<span className="font-medium text-heading dark:text-zinc-100">
					{link.target_type?.display_name ?? '?'}
				</span>
				<span className="font-mono">.{link.target_column}</span>
				<span className={`${BADGE} ${BADGE_TONE.grey}`}>{ORIGIN_LABEL[link.origin]}</span>
				{link.status === 'candidate' && (
					<span className={`${BADGE} ${BADGE_TONE.amber}`}>待确认</span>
				)}
				{!outgoing && <span className="text-[11px]">（指向本对象）</span>}
			</p>
			<div className="flex flex-wrap items-center gap-2">
				<label className="flex items-center gap-1 text-[11px] text-secondary">
					正向名称
					<input
						className={`${INPUT_DENSE} w-36`}
						value={forward}
						onChange={(e) => setForward(e.target.value)}
					/>
				</label>
				<label className="flex items-center gap-1 text-[11px] text-secondary">
					反向名称
					<input
						className={`${INPUT_DENSE} w-36`}
						value={reverse}
						onChange={(e) => setReverse(e.target.value)}
					/>
				</label>
				{dirty && (
					<Button
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						onClick={() =>
							act(
								linkTypesApi.update(link.id, {
									display_name: forward,
									reverse_display_name: reverse,
								}),
							)
						}
					>
						保存名称
					</Button>
				)}
				{link.status === 'candidate' && (
					<Button
						theme={ButtonTheme.Soft}
						size={Size.SMALL}
						onClick={() => act(linkTypesApi.update(link.id, { status: 'active' }))}
					>
						确认
					</Button>
				)}
				<Button
					theme={ButtonTheme.DangerSubtle}
					size={Size.SMALL}
					onClick={() => act(linkTypesApi.remove(link.id))}
				>
					删除
				</Button>
			</div>
		</li>
	);
};

export const ObjectTypeEditor = ({
	typeId,
	allTypes,
	onClose,
	onSaved,
}: {
	typeId: string;
	allTypes: ObjectType[];
	onClose: () => void;
	onSaved: () => void;
}) => {
	const [detail, setDetail] = useState<ObjectTypeDetail | null>(null);
	const [name, setName] = useState('');
	const [description, setDescription] = useState('');
	const [pk, setPk] = useState('');
	const [title, setTitle] = useState('');
	const [props, setProps] = useState<PropertyDraft[]>([]);
	const [newLink, setNewLink] = useState({ source_column: '', target: '' });
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		const res = await objectTypesApi.get(typeId);
		if (res.error) {
			setError(res.message ?? '加载失败');
			return;
		}
		setDetail(res);
		setName(res.display_name);
		setDescription(res.description ?? '');
		setPk(res.pk_column);
		setTitle(res.title_column ?? '');
		setProps(
			res.properties.map((p) => ({
				column_name: p.column_name,
				display_name: p.display_name ?? '',
				hidden: p.hidden,
			})),
		);
	}, [typeId]);

	// Links are saved one by one, so reloading them must not reset the type's unsaved edits.
	const reloadLinks = useCallback(async () => {
		const res = await objectTypesApi.get(typeId);
		if (!res.error) setDetail(res);
		onSaved();
	}, [typeId, onSaved]);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
	}, [load]);

	const save = async () => {
		setSaving(true);
		const res = await objectTypesApi.update(typeId, {
			display_name: name,
			description: description.trim() || null,
			pk_column: pk,
			title_column: title || null,
			properties: props.map((p) => ({
				column_name: p.column_name,
				display_name: p.display_name.trim() || null,
				hidden: p.hidden,
			})),
		});
		setSaving(false);
		if (res.error) {
			setError(res.message ?? '保存失败');
			return;
		}
		onSaved();
		onClose();
	};

	const addLink = async () => {
		const res = await linkTypesApi.create({
			object_type_id: typeId,
			source_column: newLink.source_column,
			target_object_type_id: newLink.target,
		});
		if (res.error) {
			setError(res.message ?? '添加失败');
			return;
		}
		setNewLink({ source_column: '', target: '' });
		await reloadLinks();
	};

	if (!detail) {
		return (
			<div className="p-5 text-xs text-secondary">
				{error ? <span className={NOTICE_ERROR}>{error}</span> : '加载中…'}
			</div>
		);
	}

	return (
		<div className="flex max-h-[85vh] flex-col">
			<div className="border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
				<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
					编辑对象类型
				</h2>
				<p className="mt-0.5 font-mono text-[11px] text-secondary">
					{detail.database_name}.{detail.schema_name}.{detail.table_name}
				</p>
			</div>
			<div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
				<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<label className={LABEL}>
						对象名称
						<input
							className={INPUT}
							value={name}
							onChange={(e) => setName(e.target.value)}
						/>
					</label>
					<div className="grid grid-cols-2 gap-3">
						<label className={LABEL}>
							主键
							<select
								className={INPUT}
								value={pk}
								onChange={(e) => setPk(e.target.value)}
							>
								{detail.properties.map((p) => (
									<option key={p.column_name} value={p.column_name}>
										{p.column_name}
									</option>
								))}
							</select>
						</label>
						<label className={LABEL}>
							标题字段
							<select
								className={INPUT}
								value={title}
								onChange={(e) => setTitle(e.target.value)}
							>
								<option value="">（用主键）</option>
								{detail.properties.map((p) => (
									<option key={p.column_name} value={p.column_name}>
										{p.column_name}
									</option>
								))}
							</select>
						</label>
					</div>
					<label className={`${LABEL} sm:col-span-2`}>
						说明
						<textarea
							className={INPUT}
							rows={2}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
						/>
					</label>
				</div>

				<section>
					<h3 className={SECTION_TITLE}>属性</h3>
					<p className="mt-0.5 text-[11px] text-secondary">
						属性即数据表的字段。留空名称时使用字段说明；隐藏的属性不在对象页展示，但仍可用于关联。
					</p>
					<table className="mt-2 w-full text-left text-xs">
						<thead className="text-secondary">
							<tr>
								<th className="py-1 font-medium">字段</th>
								<th className="py-1 font-medium">显示名称</th>
								<th className="w-14 py-1 text-center font-medium">隐藏</th>
							</tr>
						</thead>
						<tbody>
							{props.map((p, i) => {
								const source = detail.properties[i];
								return (
									<tr
										key={p.column_name}
										className="border-t border-zinc-100 dark:border-zinc-800"
									>
										<td className="py-1.5 pr-2">
											<span className="font-mono">{p.column_name}</span>
											{source.data_type && (
												<span className="ml-1 text-[11px] text-secondary">
													{source.data_type}
												</span>
											)}
										</td>
										<td className="py-1.5 pr-2">
											<input
												className={INPUT_DENSE}
												value={p.display_name}
												placeholder={source.label}
												onChange={(e) =>
													setProps(
														props.map((q, j) =>
															j === i
																? {
																		...q,
																		display_name:
																			e.target.value,
																	}
																: q,
														),
													)
												}
											/>
										</td>
										<td className="py-1.5 text-center">
											<input
												type="checkbox"
												checked={p.hidden}
												aria-label={`隐藏 ${p.column_name}`}
												onChange={(e) =>
													setProps(
														props.map((q, j) =>
															j === i
																? { ...q, hidden: e.target.checked }
																: q,
														),
													)
												}
											/>
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</section>

				<section>
					<h3 className={SECTION_TITLE}>关系</h3>
					{detail.links.length === 0 ? (
						<p className="mt-1 text-xs text-secondary">还没有关系。</p>
					) : (
						<ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
							{detail.links.map((link) => (
								<LinkRow
									key={`${link.id}-${link.display_name}-${link.reverse_display_name}-${link.status}`}
									link={link}
									typeId={typeId}
									onChanged={() => void reloadLinks()}
									onError={setError}
								/>
							))}
						</ul>
					)}
					<div className="mt-3 flex flex-wrap items-end gap-2">
						<label className={LABEL}>
							本对象的字段
							<select
								className={INPUT_DENSE}
								value={newLink.source_column}
								onChange={(e) =>
									setNewLink({ ...newLink, source_column: e.target.value })
								}
							>
								<option value="">选择字段</option>
								{detail.properties.map((p) => (
									<option key={p.column_name} value={p.column_name}>
										{p.column_name}
									</option>
								))}
							</select>
						</label>
						<label className={LABEL}>
							指向对象（按其主键匹配）
							<select
								className={INPUT_DENSE}
								value={newLink.target}
								onChange={(e) => setNewLink({ ...newLink, target: e.target.value })}
							>
								<option value="">选择对象类型</option>
								{allTypes.map((t) => (
									<option key={t.id} value={t.id}>
										{t.display_name}
									</option>
								))}
							</select>
						</label>
						<Button
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							disabled={!newLink.source_column || !newLink.target}
							onClick={() => void addLink()}
						>
							添加关系
						</Button>
					</div>
				</section>
				{error && (
					<p role="alert" className={NOTICE_ERROR}>
						{error}
					</p>
				)}
			</div>
			<div className="flex justify-end gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">
				<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onClose}>
					取消
				</Button>
				<Button
					theme={ButtonTheme.Primary}
					size={Size.SMALL}
					disabled={saving || !name.trim()}
					onClick={() => void save()}
				>
					{saving ? '保存中…' : '保存'}
				</Button>
			</div>
		</div>
	);
};
