// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { SkeletonBlock } from '@/common/Skeleton';

type SuggestedQuestionsProps = {
	/** `null` while loading. */
	questions: string[] | null;
	onPick: (question: string) => void;
	/** Shown when there is nothing certified yet. */
	emptyHint?: string;
};

/** Certified questions as one-click starting points. */
export const SuggestedQuestions = ({ questions, onPick, emptyHint }: SuggestedQuestionsProps) => {
	if (questions === null) {
		return (
			<div className="flex flex-wrap gap-2" aria-hidden>
				<SkeletonBlock className="h-8 w-40" />
				<SkeletonBlock className="h-8 w-52" />
				<SkeletonBlock className="h-8 w-36" />
			</div>
		);
	}
	if (questions.length === 0) {
		return emptyHint ? <p className="text-xs text-secondary">{emptyHint}</p> : null;
	}
	return (
		<ul className="flex flex-wrap gap-2" aria-label="推荐问题">
			{questions.map((question) => (
				<li key={question}>
					<button
						type="button"
						onClick={() => onPick(question)}
						className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-left text-xs text-body transition-colors hover:border-[#2563eb]/50 hover:bg-[#2563eb]/5 hover:text-[#1d4ed8] dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:text-[#93c5fd]"
					>
						{question}
					</button>
				</li>
			))}
		</ul>
	);
};
