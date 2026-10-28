// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useRef } from 'react';
import type { ChatMessage, GraphStep } from '@/types/chat';
import { EmptyState } from '@/common/EmptyState';
import { Icon, IconName } from '@/common/icons';
import { SkeletonBlock } from '@/common/Skeleton';
import { EmptyStateVariant } from '@/enums/emptyState';
import { MessageBubble } from './MessageBubble';
import { ThinkingMessage } from './ThinkingMessage';

type MessageListProps = {
	messages: ChatMessage[];
	isLoading: boolean;
	steps: GraphStep[];
	/** SQL the running agent has produced but not finished executing. */
	liveSql?: string | null;
	messageListLoading?: boolean;
	/** The open conversation, for rating its answers. */
	conversationId?: string | null;
};

export const MessageList = ({
	messages,
	isLoading,
	steps,
	liveSql,
	messageListLoading = false,
	conversationId = null,
}: MessageListProps) => {
	const bottomRef = useRef<HTMLDivElement>(null);

	// Re-pin to the bottom whenever the rendered content grows. `steps` is
	// tracked by identity rather than length because a step event that only
	// attaches a node's thought keeps the list the same length while making it
	// taller, and `liveSql` because the SQL block lands between step events —
	// neither would scroll into view otherwise.
	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
	}, [messages.length, isLoading, steps, liveSql]);

	if (messageListLoading) {
		return (
			<div className="flex flex-1 flex-col gap-4 p-6" role="status" aria-label="正在加载消息">
				<SkeletonBlock className="h-16 w-2/3" />
				<SkeletonBlock className="ml-auto h-12 w-1/2" />
				<SkeletonBlock className="h-20 w-3/5" />
			</div>
		);
	}

	if (messages.length === 0 && !isLoading) {
		return (
			<EmptyState
				variant={EmptyStateVariant.Welcome}
				illustration={
					<div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#2563eb]/15">
						<Icon name={IconName.ChatBubble} className="h-7 w-7 text-[#2563eb]" />
					</div>
				}
				title="提出问题"
				description="用自然语言输入问题，系统会检索你的数据、生成 SQL 查询并返回结果。"
			/>
		);
	}

	return (
		<div className="flex-1 overflow-y-auto">
			<div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
				{messages.map((msg, index) => (
					<MessageBubble
						key={msg.id}
						message={msg}
						conversationId={conversationId}
						question={
							msg.role === 'assistant'
								? messages
										.slice(0, index)
										.reverse()
										.find((m) => m.role === 'user')?.content
								: undefined
						}
					/>
				))}
				{isLoading && <ThinkingMessage steps={steps} liveSql={liveSql} />}
				<div ref={bottomRef} />
			</div>
		</div>
	);
};
