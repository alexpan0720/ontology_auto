// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { conversationsApi, type ConversationSummary } from '@/api/conversations';
import { objectTypesApi } from '@/api/objects';
import { formatDate } from '@/common/date';
import { Icon, IconName } from '@/common/icons';
import { objectHref } from '@/components/objectsPage/format';
import { askHref, useSuggestedQuestions } from '@/hooks/useSuggestedQuestions';
import { navItem } from '@/lib/navigation';
import type { ObjectType } from '@/types/objects';
import { AdminTodos } from './AdminTodos';
import { AskBox } from './AskBox';
import { SuggestedQuestions } from './SuggestedQuestions';

const RECENT_LIMIT = 5;
const OBJECT_LIMIT = 8;
const SHORTCUTS = ['objects', 'terms', 'data', 'analysis'].map(navItem);

const SECTION_TITLE = 'text-sm font-semibold text-heading dark:text-zinc-100';
const PANEL =
	'rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900';

/** Loads once; `null` while loading, `[]` when it failed or there is nothing. */
const useList = <T,>(load: () => Promise<T[]>): T[] | null => {
	const [rows, setRows] = useState<T[] | null>(null);
	useEffect(() => {
		let active = true;
		load()
			.then((data) => active && setRows(data))
			.catch(() => active && setRows([]));
		return () => {
			active = false;
		};
		// `load` is a module-level reader; reading it once on mount is the intent.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);
	return rows;
};

const loadRecent = async (): Promise<ConversationSummary[]> =>
	(await conversationsApi.list()).slice(0, RECENT_LIMIT);

const loadObjects = async (): Promise<ObjectType[]> => {
	const res = await objectTypesApi.list('active');
	return res.error ? [] : res.data;
};

const Placeholder = ({ rows }: { rows: number }) => (
	<div className="space-y-2" aria-hidden>
		{Array.from({ length: rows }, (_, i) => (
			<div key={i} className="h-5 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
		))}
	</div>
);

export type HomeViewProps = {
	userName?: string | null;
	isAdmin?: boolean;
};

/**
 * Where everyone lands: ask a question, or pick up where they left off. An
 * admin also sees what is waiting on them, above the rest.
 */
export const HomeView = ({ userName, isAdmin = false }: HomeViewProps) => {
	const router = useRouter();
	const suggestions = useSuggestedQuestions();
	const recent = useList(loadRecent);
	const objects = useList(loadObjects);

	const ask = (question: string) => router.push(askHref(question));

	return (
		<div className="h-full overflow-y-auto bg-zinc-50/60 dark:bg-zinc-950">
			<div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
				<section aria-labelledby="home-ask-title" className="mx-auto w-full max-w-3xl">
					<h1
						id="home-ask-title"
						className="text-center text-2xl font-semibold tracking-tight text-heading dark:text-zinc-100"
					>
						{userName ? `${userName}，你想了解什么？` : '你想了解什么？'}
					</h1>
					<p className="mt-1 text-center text-sm text-secondary dark:text-zinc-400">
						用日常的话提问，系统会找到对应的数据，给出结果、图表和数据来源。
					</p>
					<div className="mt-5">
						<AskBox onAsk={ask} />
					</div>
					<div className="mt-3">
						<SuggestedQuestions
							questions={suggestions}
							onPick={ask}
							emptyHint={
								isAdmin
									? '在「管理中心 → 认证问答库」认证常见问题后，它们会作为推荐问题出现在这里。'
									: undefined
							}
						/>
					</div>
				</section>

				{isAdmin && <AdminTodos />}

				<div className="grid gap-4 lg:grid-cols-2">
					<section aria-labelledby="home-recent" className={PANEL}>
						<div className="mb-3 flex items-center justify-between">
							<h2 id="home-recent" className={SECTION_TITLE}>
								最近的对话
							</h2>
							<Link
								href="/chat"
								className="text-xs text-secondary hover:text-[#1d4ed8]"
							>
								全部对话
							</Link>
						</div>
						{recent === null ? (
							<Placeholder rows={3} />
						) : recent.length === 0 ? (
							<p className="text-xs text-secondary">
								还没有对话。在上面输入一个问题开始吧。
							</p>
						) : (
							<ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
								{recent.map((conversation) => (
									<li key={conversation.id}>
										<Link
											href={`/chat?focus=${encodeURIComponent(conversation.id)}`}
											className="flex items-center gap-3 py-2 text-sm text-body hover:text-[#1d4ed8] dark:text-zinc-300"
										>
											<Icon
												name={IconName.ChatBubble}
												className="h-4 w-4 shrink-0 text-secondary"
											/>
											<span className="min-w-0 flex-1 truncate">
												{conversation.title || '未命名对话'}
											</span>
											<span className="shrink-0 text-[11px] text-secondary">
												{formatDate(conversation.updated_at, 'MM-DD HH:mm')}
											</span>
										</Link>
									</li>
								))}
							</ul>
						)}
					</section>

					<section aria-labelledby="home-objects" className={PANEL}>
						<div className="mb-3 flex items-center justify-between">
							<h2 id="home-objects" className={SECTION_TITLE}>
								业务对象
							</h2>
							<Link
								href="/objects"
								className="text-xs text-secondary hover:text-[#1d4ed8]"
							>
								全部对象
							</Link>
						</div>
						{objects === null ? (
							<Placeholder rows={2} />
						) : objects.length === 0 ? (
							<p className="text-xs text-secondary">
								{isAdmin
									? '还没有确认的业务对象。可在「管理中心 → 对象类型」从数据目录一键生成。'
									: '管理员确认业务对象后，会显示在这里。'}
							</p>
						) : (
							<ul className="flex flex-wrap gap-2">
								{objects.slice(0, OBJECT_LIMIT).map((type) => (
									<li key={type.id}>
										<Link
											href={objectHref(type.id)}
											className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-sm text-body hover:border-[#2563eb]/50 hover:text-[#1d4ed8] dark:border-zinc-700 dark:text-zinc-300"
										>
											<Icon
												name={IconName.Cube}
												className="h-4 w-4 text-[#2563eb]"
											/>
											{type.display_name}
										</Link>
									</li>
								))}
							</ul>
						)}
					</section>
				</div>

				<section aria-labelledby="home-shortcuts">
					<h2 id="home-shortcuts" className={`${SECTION_TITLE} mb-2`}>
						常用入口
					</h2>
					<ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
						{SHORTCUTS.map((item) => (
							<li key={item.key}>
								<Link
									href={item.href}
									className={`${PANEL} flex h-full items-start gap-3 transition-colors hover:border-[#2563eb]/50`}
								>
									<Icon
										name={item.icon}
										className="mt-0.5 h-5 w-5 shrink-0 text-[#2563eb]"
									/>
									<span>
										<span className="block text-sm font-medium text-heading dark:text-zinc-100">
											{item.label}
										</span>
										<span className="mt-0.5 block text-xs text-secondary dark:text-zinc-400">
											{item.hint}
										</span>
									</span>
								</Link>
							</li>
						))}
					</ul>
				</section>
			</div>
		</div>
	);
};
