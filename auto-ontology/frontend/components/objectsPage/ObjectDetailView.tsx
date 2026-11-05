// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { objectTypesApi } from '@/api/objects';
import { Icon, IconName } from '@/common/icons';
import { Spinner } from '@/common/Spinner';
import {
	BADGE,
	BADGE_TONE,
	CARD,
	CARD_COMPACT,
	NOTICE_ERROR,
	SECTION_TITLE,
} from '@/components/settings/pageStyles';
import type { LinkedObjects, ObjectDetail } from '@/types/objects';
import { formatValue, objectHref } from './format';

const LinkedSection = ({ link }: { link: LinkedObjects }) => (
	<section className={CARD_COMPACT}>
		<div className="flex items-center gap-2">
			<Icon name={IconName.Link} className="h-4 w-4 text-secondary" />
			<h3 className={SECTION_TITLE}>{link.name}</h3>
			{link.many && !link.error && (
				<span className={`${BADGE} ${BADGE_TONE.grey}`}>
					{link.objects.length}
					{link.has_more ? '+' : ''}
				</span>
			)}
			<Link
				href={objectHref(link.object_type.id)}
				className="ml-auto text-[11px] text-secondary hover:text-[#1d4ed8] hover:underline"
			>
				全部{link.object_type.display_name}
			</Link>
		</div>
		{link.error ? (
			<p className={`mt-2 ${NOTICE_ERROR}`}>{link.error}</p>
		) : link.objects.length === 0 ? (
			<p className="mt-2 text-xs text-secondary">无</p>
		) : (
			<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
				{link.objects.map((o, i) => (
					<li key={o.key ?? `row-${i}`} className="py-1.5">
						{o.key != null ? (
							<Link
								href={objectHref(link.object_type.id, o.key)}
								className="text-sm font-medium text-[#1d4ed8] hover:underline dark:text-[#60a5fa]"
							>
								{o.title}
							</Link>
						) : (
							<span className="text-sm">{o.title}</span>
						)}
						<p className="truncate text-[11px] text-secondary">
							{Object.entries(o.values)
								.slice(0, 5)
								.map(([k, v]) => `${k}：${formatValue(v)}`)
								.join(' · ')}
						</p>
					</li>
				))}
			</ul>
		)}
		{link.has_more && (
			<p className="mt-1 text-[11px] text-secondary">仅显示前 {link.objects.length} 个</p>
		)}
	</section>
);

export const ObjectDetailView = ({ typeId, objectKey }: { typeId: string; objectKey: string }) => {
	const [detail, setDetail] = useState<ObjectDetail | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let cancelled = false;
		// eslint-disable-next-line react-hooks/set-state-in-effect -- reset before the fetch below
		setDetail(null);
		setError(null);
		void objectTypesApi.object(typeId, objectKey).then((res) => {
			if (cancelled) return;
			if (res.error) setError(res.message ?? '加载失败');
			else setDetail(res);
		});
		return () => {
			cancelled = true;
		};
	}, [typeId, objectKey]);

	if (error) {
		return (
			<div className="px-6 py-5">
				<p role="alert" className={NOTICE_ERROR}>
					{error}
				</p>
			</div>
		);
	}
	if (!detail) {
		return (
			<div className="flex items-center gap-2 px-6 py-5 text-xs text-secondary">
				<Spinner className="h-4 w-4" /> 正在读取…
			</div>
		);
	}

	const outgoing = detail.links.filter((l) => !l.many);
	const incoming = detail.links.filter((l) => l.many);

	return (
		<div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
			<nav className="flex items-center gap-1 text-xs text-secondary">
				<Link href="/objects" className="hover:underline">
					对象
				</Link>
				<span>/</span>
				<Link href={objectHref(detail.object_type.id)} className="hover:underline">
					{detail.object_type.display_name}
				</Link>
				<span>/</span>
				<span className="text-body dark:text-zinc-300">{detail.title}</span>
			</nav>

			<section className={CARD}>
				<div className="flex items-center gap-2">
					<span className={`${BADGE} ${BADGE_TONE.blue}`}>
						{detail.object_type.display_name}
					</span>
					<h2 className="text-lg font-semibold text-heading dark:text-zinc-100">
						{detail.title}
					</h2>
				</div>
				<dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
					{detail.properties.map((p) => (
						<div key={p.name} className="min-w-0">
							<dt className="text-[11px] text-secondary" title={p.name}>
								{p.label}
							</dt>
							<dd className="break-words text-sm text-body dark:text-zinc-200">
								{formatValue(detail.values[p.name])}
							</dd>
						</div>
					))}
				</dl>
				{outgoing.length > 0 && (
					<div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-zinc-100 pt-3 dark:border-zinc-800">
						{outgoing.map((l) => (
							<div key={`${l.link_id}-${l.direction}`} className="text-sm">
								<span className="mr-2 text-[11px] text-secondary">{l.name}</span>
								{l.error ? (
									<span className={NOTICE_ERROR}>{l.error}</span>
								) : l.objects[0]?.key != null ? (
									<Link
										href={objectHref(l.object_type.id, l.objects[0].key)}
										className="font-medium text-[#1d4ed8] hover:underline dark:text-[#60a5fa]"
									>
										{l.objects[0].title}
									</Link>
								) : (
									<span className="text-secondary">—</span>
								)}
							</div>
						))}
					</div>
				)}
			</section>

			{incoming.length > 0 && (
				<div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
					{incoming.map((l) => (
						<LinkedSection key={`${l.link_id}-${l.direction}`} link={l} />
					))}
				</div>
			)}
		</div>
	);
};
