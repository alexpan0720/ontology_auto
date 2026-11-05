// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import { verifiedQueriesApi } from '@/api/governance';

/**
 * Certified questions to offer as a start, or `null` while loading. A failed
 * read is an empty list: suggestions are a help, never a reason to show an
 * error where someone is about to ask a question.
 */
export const useSuggestedQuestions = (limit = 6): string[] | null => {
	const [questions, setQuestions] = useState<string[] | null>(null);

	useEffect(() => {
		let active = true;
		void verifiedQueriesApi.suggestions(limit).then((res) => {
			if (!active) return;
			setQuestions(res.error ? [] : res.data.map((row) => row.question));
		});
		return () => {
			active = false;
		};
	}, [limit]);

	return questions;
};

/** Where asking *question* leads: the chat page, which asks it on arrival. */
export const askHref = (question: string): string =>
	`/chat?q=${encodeURIComponent(question.trim())}`;
