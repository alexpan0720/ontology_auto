// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { navigation, nextLinkMock, nextNavigationMock, resetNavigation } from '@/test/nextMocks';
import { ChatView } from './ChatView';

vi.mock('next/navigation', () => nextNavigationMock());
vi.mock('next/link', () => nextLinkMock());

const chat = vi.hoisted(() => ({
	sendMessage: vi.fn(),
	create: vi.fn(),
	list: vi.fn(),
	status: vi.fn(),
	suggestions: vi.fn(),
	objectTypes: vi.fn(),
}));

vi.mock('@/lib/useChat', () => ({
	useChat: () => ({
		messages: [],
		setMessages: vi.fn(),
		steps: [],
		liveSql: null,
		isLoading: false,
		sendMessage: chat.sendMessage,
		resumeIfRunning: vi.fn(),
		stopGeneration: vi.fn(),
		clearConversation: vi.fn(),
	}),
}));
vi.mock('@/api/conversations', () => ({
	conversationsApi: { list: chat.list, create: chat.create, get: vi.fn() },
	toConversation: vi.fn(),
}));
vi.mock('@/api/settings', () => ({ semanticCompilationApi: { getStatus: chat.status } }));
vi.mock('@/api/governance', () => ({ verifiedQueriesApi: { suggestions: chat.suggestions } }));
vi.mock('@/api/objects', () => ({ objectTypesApi: { list: chat.objectTypes } }));

beforeEach(() => {
	Object.values(chat).forEach((fn) => fn.mockReset());
	chat.list.mockResolvedValue([]);
	chat.create.mockResolvedValue({ id: 'c9', title: '', created_at: '', updated_at: '' });
	chat.status.mockResolvedValue({ calculated: true, running: false });
	chat.sendMessage.mockResolvedValue(true);
	chat.suggestions.mockResolvedValue({
		data: [{ id: 'q1', question: '各渠道订单数' }],
		count: 1,
	});
	chat.objectTypes.mockResolvedValue({
		data: [{ id: 'customer', display_name: '客户' }],
		count: 1,
		summary: {},
	});
});

describe('ChatView', () => {
	it('asks a question carried in the URL once, then drops it from the URL', async () => {
		resetNavigation('/chat', 'q=上月 GMV');
		render(<ChatView />);

		await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith('上月 GMV', 'c9'));
		expect(chat.create).toHaveBeenCalledTimes(1);
		expect(navigation.replace).toHaveBeenCalledWith('/chat?focus=c9', { scroll: false });
	});

	it('does not ask a carried question while the semantic layer is not ready', async () => {
		chat.status.mockResolvedValue({ calculated: false, running: false });
		resetNavigation('/chat', 'q=上月 GMV');
		render(<ChatView />);
		await waitFor(() => expect(chat.status).toHaveBeenCalled());
		expect(chat.sendMessage).not.toHaveBeenCalled();
	});

	it('welcomes an empty conversation with objects and questions to ask', async () => {
		resetNavigation('/chat');
		render(<ChatView />);

		expect(await screen.findByRole('link', { name: '客户' })).toBeTruthy();
		fireEvent.click(await screen.findByRole('button', { name: '各渠道订单数' }));
		await waitFor(() => expect(chat.sendMessage).toHaveBeenCalledWith('各渠道订单数', 'c9'));
	});
});
