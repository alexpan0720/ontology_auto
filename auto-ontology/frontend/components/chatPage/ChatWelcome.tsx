// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { objectTypesApi } from '@/api/objects';
import { Icon, IconName } from '@/common/icons';
import { SuggestedQuestions } from '@/components/homePage/SuggestedQuestions';
import { objectHref } from '@/components/objectsPage/format';
import { useSuggestedQuestions } from '@/hooks/useSuggestedQuestions';
import type { ObjectType } from '@/types/objects';

const OBJECT_LIMIT = 10;

/**
 * What an empty conversation shows: what can be asked about, and questions
 * already known to answer well. A blank page with "ask a question" left
 * people guessing what the data even covers.
 */
export const ChatWelcome = ({ onAsk }: { onAsk: (question: string) => void }) => {
	const suggestions = useSuggestedQuestions();
	const [objects, setObjects] = useState<ObjectType[]>([]);

	useEffect(() => {
		let active = true;
		void objectTypesApi.list('active').then((res) => {
			if (active && !res.error) setObjects(res.data);
		});
		return () => {
			active = false;
		};
	}, []);

	return (
		<div className="flex flex-1 items-center justify-center overflow-y-auto px-6 py-10">
			<div className="w-full max-w-2xl">
				<div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#2563eb]/15">
					<Icon name={IconName.ChatBubble} className="h-6 w-6 text-[#2563eb]" />
				</div>
				<h2 className="mt-4 text-xl font-semibold text-heading dark:text-zinc-100">
					用日常的话提问
				</h2>
				<p className="mt-1 text-sm text-secondary dark:text-zinc-400">
					系统会找到对应的数据、生成查询，并给出结果、图表和数据来源。可以接着追问，例如“那华东呢？”。
				</p>

				{objects.length > 0 && (
					<section aria-labelledby="chat-objects" className="mt-6">
						<h3 id="chat-objects" className="text-xs font-medium text-secondary">
							可以问这些业务对象
						</h3>
						<ul className="mt-2 flex flex-wrap gap-2">
							{objects.slice(0, OBJECT_LIMIT).map((type) => (
								<li key={type.id}>
									<Link
										href={objectHref(type.id)}
										className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-1 text-xs text-body hover:text-[#1d4ed8] dark:bg-zinc-800 dark:text-zinc-300"
									>
										<Icon name={IconName.Cube} className="h-3.5 w-3.5" />
										{type.display_name}
									</Link>
								</li>
							))}
						</ul>
					</section>
				)}

				{(suggestions === null || suggestions.length > 0) && (
					<section aria-labelledby="chat-suggestions" className="mt-6">
						<h3
							id="chat-suggestions"
							className="mb-2 text-xs font-medium text-secondary"
						>
							试试这些问题
						</h3>
						<SuggestedQuestions questions={suggestions} onPick={onAsk} />
					</section>
				)}
			</div>
		</div>
	);
};
