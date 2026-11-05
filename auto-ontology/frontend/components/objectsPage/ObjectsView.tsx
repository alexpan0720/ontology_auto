// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { objectTypesApi } from '@/api/objects';
import { EmptyState } from '@/common/EmptyState';
import { Icon, IconName } from '@/common/icons';
import { SearchInput } from '@/common/SearchInput';
import { Spinner } from '@/common/Spinner';
import { CARD_COMPACT, NOTICE_ERROR } from '@/components/settings/pageStyles';
import type { ObjectType } from '@/types/objects';
import { ObjectDetailView } from './ObjectDetailView';
import { ObjectListView } from './ObjectListView';
import { objectHref } from './format';

const Overview = ({ types }: { types: ObjectType[] }) =>
	types.length === 0 ? (
		<div className="px-6 py-10">
			<EmptyState
				icon={IconName.Cube}
				title="还没有业务对象"
				description="管理员可在「设置 → 对象类型」中，从数据目录的主键和外键一键生成客户、订单等业务对象及其关系。"
			/>
		</div>
	) : (
		<div className="grid grid-cols-1 gap-3 overflow-y-auto px-6 py-5 sm:grid-cols-2 xl:grid-cols-3">
			{types.map((t) => (
				<Link
					key={t.id}
					href={objectHref(t.id)}
					className={`${CARD_COMPACT} block transition-colors hover:border-[#2563eb]/50`}
				>
					<div className="flex items-center gap-2">
						<Icon name={IconName.Cube} className="h-4 w-4 text-[#2563eb]" />
						<span className="text-sm font-semibold text-heading dark:text-zinc-100">
							{t.display_name}
						</span>
						<span className="ml-auto text-[11px] text-secondary">
							{t.link_count} 个关系
						</span>
					</div>
					<p className="mt-1 line-clamp-2 text-xs text-secondary dark:text-zinc-400">
						{t.description || '—'}
					</p>
					<p className="mt-2 truncate font-mono text-[11px] text-secondary">
						{t.schema_name}.{t.table_name}
					</p>
				</Link>
			))}
		</div>
	);

export const ObjectsView = () => {
	const searchParams = useSearchParams();
	const typeId = searchParams.get('type');
	const objectKey = searchParams.get('key');
	const [types, setTypes] = useState<ObjectType[] | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [filter, setFilter] = useState('');

	useEffect(() => {
		void objectTypesApi.list('active').then((res) => {
			if (res.error) {
				setError(res.message ?? '加载失败');
				setTypes([]);
				return;
			}
			setTypes(res.data);
		});
	}, []);

	const visible = useMemo(() => {
		const needle = filter.trim().toLowerCase();
		if (!types || !needle) return types ?? [];
		return types.filter(
			(t) =>
				t.display_name.toLowerCase().includes(needle) ||
				t.table_name.toLowerCase().includes(needle),
		);
	}, [types, filter]);

	const selected = types?.find((t) => t.id === typeId) ?? null;

	return (
		<div className="flex h-full w-full flex-col bg-white dark:bg-zinc-950">
			<header className="flex items-center gap-3 border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
				<Icon name={IconName.Cube} className="h-5 w-5 text-body dark:text-zinc-300" />
				<h1 className="text-lg font-semibold tracking-tight text-heading dark:text-zinc-100">
					对象
				</h1>
				<p className="text-xs text-secondary">
					以业务对象查看数据：客户、订单及其之间的关系。按你的数据权限读取。
				</p>
			</header>
			<div className="flex min-h-0 flex-1">
				<aside className="flex w-60 shrink-0 flex-col gap-2 border-r border-zinc-200 p-3 dark:border-zinc-800">
					<SearchInput
						value={filter}
						onChange={setFilter}
						placeholder="筛选对象类型"
						aria-label="筛选对象类型"
					/>
					<nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
						<Link
							href="/objects"
							className={`rounded-md px-2 py-1.5 text-sm ${
								!typeId
									? 'bg-[#2563eb]/10 font-medium text-heading dark:text-zinc-100'
									: 'text-body hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800'
							}`}
						>
							全部对象类型
						</Link>
						{visible.map((t) => (
							<Link
								key={t.id}
								href={objectHref(t.id)}
								className={`truncate rounded-md px-2 py-1.5 text-sm ${
									t.id === typeId
										? 'bg-[#2563eb]/10 font-medium text-heading dark:text-zinc-100'
										: 'text-body hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800'
								}`}
							>
								{t.display_name}
							</Link>
						))}
					</nav>
				</aside>
				<main className="flex min-h-0 min-w-0 flex-1 flex-col">
					{error && <p className={`px-6 pt-4 ${NOTICE_ERROR}`}>{error}</p>}
					{types === null ? (
						<div className="flex items-center gap-2 px-6 py-5 text-xs text-secondary">
							<Spinner className="h-4 w-4" /> 正在加载…
						</div>
					) : typeId && objectKey ? (
						<ObjectDetailView typeId={typeId} objectKey={objectKey} />
					) : selected ? (
						<ObjectListView key={selected.id} objectType={selected} />
					) : typeId ? (
						<p className="px-6 py-5 text-xs text-secondary">
							这个对象类型不存在或尚未确认。
						</p>
					) : (
						<Overview types={types} />
					)}
				</main>
			</div>
		</div>
	);
};
