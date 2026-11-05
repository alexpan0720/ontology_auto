// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { objectTypesApi } from '@/api/objects';
import { Button } from '@/common/Button';
import { SearchInput } from '@/common/SearchInput';
import { Spinner } from '@/common/Spinner';
import { NOTICE_ERROR, PAGE_INTRO, PAGE_TITLE } from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type { ObjectPage, ObjectType } from '@/types/objects';
import { formatValue, objectHref } from './format';

const PAGE_SIZE = 50;

export const ObjectListView = ({ objectType }: { objectType: ObjectType }) => {
	const [search, setSearch] = useState('');
	const [query, setQuery] = useState('');
	const [offset, setOffset] = useState(0);
	const [page, setPage] = useState<ObjectPage | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// Typing waits for a pause before querying the source database.
	useEffect(() => {
		const timer = setTimeout(() => {
			setQuery(search.trim());
			setOffset(0);
		}, 350);
		return () => clearTimeout(timer);
	}, [search]);

	useEffect(() => {
		let cancelled = false;
		// eslint-disable-next-line react-hooks/set-state-in-effect -- loading flag for the fetch below
		setLoading(true);
		void objectTypesApi
			.objects(objectType.id, { search: query || undefined, limit: PAGE_SIZE, offset })
			.then((res) => {
				if (cancelled) return;
				setLoading(false);
				if (res.error) {
					setError(res.message ?? '加载失败');
					setPage(null);
					return;
				}
				setError(null);
				setPage(res);
			});
		return () => {
			cancelled = true;
		};
	}, [objectType.id, query, offset]);

	return (
		<div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<div>
					<h2 className={PAGE_TITLE}>{objectType.display_name}</h2>
					<p className={PAGE_INTRO}>
						{objectType.description || '—'}
						<span className="ml-2 font-mono text-[11px] text-secondary">
							{objectType.database_name}.{objectType.schema_name}.
							{objectType.table_name}
						</span>
					</p>
				</div>
				<SearchInput
					value={search}
					onChange={setSearch}
					placeholder="按名称或编号搜索"
					className="w-64"
					aria-label="搜索对象"
				/>
			</div>

			{error && (
				<p role="alert" className={NOTICE_ERROR}>
					{error}
				</p>
			)}

			{loading && !page ? (
				<div className="flex items-center gap-2 text-xs text-secondary">
					<Spinner className="h-4 w-4" /> 正在读取…
				</div>
			) : page && page.objects.length === 0 ? (
				<p className="text-xs text-secondary">
					{query ? '没有匹配的对象。' : '没有可查看的对象。'}
				</p>
			) : (
				page && (
					<div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
						<table className="w-full text-left text-xs">
							<thead className="bg-zinc-50 text-secondary dark:bg-zinc-900 dark:text-zinc-400">
								<tr>
									{page.columns.map((c) => (
										<th
											key={c.name}
											className="whitespace-nowrap px-3 py-2 font-medium"
											title={c.name}
										>
											{c.label}
										</th>
									))}
								</tr>
							</thead>
							<tbody className={loading ? 'opacity-60' : ''}>
								{page.objects.map((o, i) => (
									<tr
										key={o.key ?? `row-${i}`}
										className="border-t border-zinc-100 hover:bg-[#2563eb]/5 dark:border-zinc-800"
									>
										{page.columns.map((c, ci) => (
											<td
												key={c.name}
												className="max-w-xs truncate px-3 py-2 text-body dark:text-zinc-300"
											>
												{ci === 0 && o.key != null ? (
													<Link
														href={objectHref(objectType.id, o.key)}
														className="font-medium text-[#1d4ed8] hover:underline dark:text-[#60a5fa]"
													>
														{formatValue(o.values[c.name])}
													</Link>
												) : c.name === page.title_column &&
												  o.key != null ? (
													<Link
														href={objectHref(objectType.id, o.key)}
														className="hover:underline"
													>
														{formatValue(o.values[c.name])}
													</Link>
												) : (
													formatValue(o.values[c.name])
												)}
											</td>
										))}
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)
			)}

			{page && (offset > 0 || page.has_more) && (
				<div className="flex items-center justify-end gap-2 text-xs text-secondary">
					<span>
						第 {offset + 1}–{offset + page.objects.length} 个
					</span>
					<Button
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						disabled={offset === 0 || loading}
						onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
					>
						上一页
					</Button>
					<Button
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						disabled={!page.has_more || loading}
						onClick={() => setOffset(offset + PAGE_SIZE)}
					>
						下一页
					</Button>
				</div>
			)}
		</div>
	);
};
