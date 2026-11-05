// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { navigation, nextLinkMock, nextNavigationMock, resetNavigation } from '@/test/nextMocks';
import { HomeView } from './HomeView';

vi.mock('next/navigation', () => nextNavigationMock());
vi.mock('next/link', () => nextLinkMock());

const api = vi.hoisted(() => ({
	conversations: vi.fn(),
	objectTypes: vi.fn(),
	suggestions: vi.fn(),
	verifiedList: vi.fn(),
	accessRequests: vi.fn(),
	insights: vi.fn(),
	semantic: vi.fn(),
}));

vi.mock('@/api/conversations', () => ({ conversationsApi: { list: api.conversations } }));
vi.mock('@/api/objects', () => ({ objectTypesApi: { list: api.objectTypes } }));
vi.mock('@/api/governance', () => ({
	verifiedQueriesApi: { suggestions: api.suggestions, list: api.verifiedList },
}));
vi.mock('@/api/accessRequests', () => ({ accessRequestsApi: { list: api.accessRequests } }));
vi.mock('@/api/insights', () => ({ insightsApi: { board: api.insights } }));
vi.mock('@/api/settings', () => ({ semanticCompilationApi: { getStatus: api.semantic } }));

const SUMMARY = { active_types: 1, candidate_types: 0, active_links: 0, candidate_links: 0 };

const OBJECT = {
	id: 'customer',
	display_name: '客户',
	table_name: 'customers',
};

beforeEach(() => {
	resetNavigation('/home');
	Object.values(api).forEach((fn) => fn.mockReset());
	api.conversations.mockResolvedValue([
		{ id: 'c1', title: '上月销售', created_at: '', updated_at: '2026-11-01T08:00:00Z' },
	]);
	api.objectTypes.mockResolvedValue({ data: [OBJECT], count: 1, summary: SUMMARY });
	api.suggestions.mockResolvedValue({
		data: [{ id: 'q1', question: '各渠道订单数' }],
		count: 1,
	});
});

describe('HomeView', () => {
	it('greets by name and asks in the chat', async () => {
		render(<HomeView userName="小潘" />);
		expect(
			screen.getByRole('heading', { level: 1, name: '小潘，你想了解什么？' }),
		).toBeTruthy();

		const box = screen.getByLabelText('你的问题');
		fireEvent.change(box, { target: { value: '  上月 GMV  ' } });
		fireEvent.keyDown(box, { key: 'Enter' });
		expect(navigation.push).toHaveBeenCalledWith('/chat?q=%E4%B8%8A%E6%9C%88%20GMV');
	});

	it('does not ask an empty question', () => {
		render(<HomeView />);
		const ask = screen.getByRole('button', { name: '提问' }) as HTMLButtonElement;
		expect(ask.disabled).toBe(true);
		fireEvent.keyDown(screen.getByLabelText('你的问题'), { key: 'Enter' });
		expect(navigation.push).not.toHaveBeenCalled();
	});

	it('asks a suggested question in one click', async () => {
		render(<HomeView />);
		fireEvent.click(await screen.findByRole('button', { name: '各渠道订单数' }));
		expect(navigation.push).toHaveBeenCalledWith(
			`/chat?q=${encodeURIComponent('各渠道订单数')}`,
		);
	});

	it('links recent conversations and business objects', async () => {
		render(<HomeView />);
		const recent = await screen.findByRole('link', { name: /上月销售/ });
		expect(recent.getAttribute('href')).toBe('/chat?focus=c1');
		const object = await screen.findByRole('link', { name: '客户' });
		expect(object.getAttribute('href')).toBe('/objects?type=customer');
	});

	it('tells a viewer who will set up objects, without admin to-dos', async () => {
		api.objectTypes.mockResolvedValue({ data: [], count: 0, summary: SUMMARY });
		api.suggestions.mockResolvedValue({ error: true, message: 'x' });
		render(<HomeView />);
		expect(await screen.findByText('管理员确认业务对象后，会显示在这里。')).toBeTruthy();
		expect(screen.queryByText('管理待办')).toBeNull();
		expect(screen.queryByRole('list', { name: '推荐问题' })).toBeNull();
	});
});

describe('HomeView for an admin', () => {
	beforeEach(() => {
		api.accessRequests.mockResolvedValue({ data: [], count: 0, pending: 2 });
		api.objectTypes.mockResolvedValue({
			data: [OBJECT],
			count: 1,
			summary: { ...SUMMARY, candidate_types: 3, candidate_links: 1 },
		});
		api.verifiedList.mockResolvedValue({ data: [], count: 0 });
		api.insights.mockRejectedValue(new Error('down'));
		api.semantic.mockResolvedValue({ calculated: true, running: false });
	});

	it('shows what is waiting, and survives one source failing', async () => {
		render(<HomeView isAdmin />);
		const todos = await screen.findByRole('region', { name: '管理待办' });

		const requests = await within(todos).findByRole('link', { name: /待审批的权限申请/ });
		expect(requests.textContent).toContain('2');
		expect(requests.getAttribute('href')).toBe('/settings/access-requests');

		const objects = within(todos).getByRole('link', { name: /待确认的业务对象/ });
		expect(objects.textContent).toContain('4');

		const insights = within(todos).getByRole('link', { name: /没答好的问题/ });
		expect(insights.textContent).toContain('—');

		const semantic = within(todos).getByRole('link', { name: /语义层/ });
		expect(semantic.textContent).toContain('已就绪');
	});

	it('points an admin to where suggestions come from', async () => {
		api.suggestions.mockResolvedValue({ data: [], count: 0 });
		render(<HomeView isAdmin />);
		expect(await screen.findByText(/认证问答库/)).toBeTruthy();
	});
});
