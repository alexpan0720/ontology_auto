// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { Button } from '@/common/Button';
import { ButtonTheme, Size } from '@/enums/button';

/**
 * The question box on the home page. Enter asks, Shift+Enter starts a new
 * line, as in the chat itself.
 */
export const AskBox = ({ onAsk }: { onAsk: (question: string) => void }) => {
	const [question, setQuestion] = useState('');
	const ready = question.trim().length > 0;

	const submit = (event?: FormEvent) => {
		event?.preventDefault();
		if (ready) onAsk(question.trim());
	};

	const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
		if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
			event.preventDefault();
			submit();
		}
	};

	return (
		<form
			onSubmit={submit}
			className="flex items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 shadow-sm focus-within:border-[#2563eb] focus-within:ring-2 focus-within:ring-[#2563eb]/15 dark:border-zinc-700 dark:bg-zinc-900"
		>
			<label htmlFor="home-ask" className="sr-only">
				你的问题
			</label>
			<textarea
				id="home-ask"
				rows={2}
				value={question}
				onChange={(event) => setQuestion(event.target.value)}
				onKeyDown={onKeyDown}
				placeholder="例如：上个月各渠道的销售额是多少？"
				className="min-h-[52px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-heading outline-none placeholder:text-secondary dark:text-zinc-100"
			/>
			<Button theme={ButtonTheme.Primary} size={Size.REGULAR} type="submit" disabled={!ready}>
				提问
			</Button>
		</form>
	);
};
