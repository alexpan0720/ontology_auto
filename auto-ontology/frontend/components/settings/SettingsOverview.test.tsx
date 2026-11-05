// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextLinkMock, nextNavigationMock, resetNavigation } from '@/test/nextMocks';
import { SettingsOverview, readSetupSteps } from './SettingsOverview';

vi.mock('next/navigation', () => nextNavigationMock());
vi.mock('next/link', () => nextLinkMock());

const api = vi.hoisted(() => ({
	connections: vi.fn(),
	semantic: vi.fn(),
	objectTypes: vi.fn(),
	verifiedList: vi.fn(),
	accessRequests: vi.fn(),
	insights: vi.fn(),
}));

vi.mock('@/api/connections', () => ({ connectionsApi: { getAll: api.connections } }));
vi.mock('@/api/settings', () => ({ semanticCompilationApi: { getStatus: api.semantic } }));
vi.mock('@/api/objects', () => ({ objectTypesApi: { list: api.objectTypes } }));
vi.mock('@/api/governance', () => ({ verifiedQueriesApi: { list: api.verifiedList } }));
vi.mock('@/api/accessRequests', () => ({ accessRequestsApi: { list: api.accessRequests } }));
vi.mock('@/api/insights', () => ({ insightsApi: { board: api.insights } }));

const SUMMARY = { active_types: 0, candidate_types: 2, active_links: 0, candidate_links: 0 };

beforeEach(() => {
	resetNavigation('/settings');
	Object.values(api).forEach((fn) => fn.mockReset());
	api.connections.mockResolvedValue({ data: [{ id: 'c' }], count: 1 });
	api.semantic.mockResolvedValue({ calculated: true, running: false });
	api.objectTypes.mockResolvedValue({ data: [], count: 0, summary: SUMMARY });
	api.verifiedList.mockResolvedValue({ data: [], count: 0 });
	api.accessRequests.mockResolvedValue({ data: [], count: 0, pending: 0 });
	api.insights.mockResolvedValue({ groups: [] });
});

describe('readSetupSteps', () => {
	it('walks the setup in order and knows what is done', async () => {
		const steps = await readSetupSteps(false);
		expect(steps.map((step) => [step.key, step.done])).toEqual([
			['connect', true],
			['compile', true],
			['objects', false],
			['certify', false],
		]);
	});

	it('counts environment-managed connections as done without reading them', async () => {
		const [connect] = await readSetupSteps(true);
		expect(connect.done).toBe(true);
		expect(api.connections).not.toHaveBeenCalled();
	});

	it('leaves a step unknown when its check fails', async () => {
		api.semantic.mockRejectedValue(new Error('down'));
		api.connections.mockResolvedValue({ error: true, message: 'x' });
		const steps = await readSetupSteps(false);
		expect(steps[0].done).toBeNull();
		expect(steps[1].done).toBeNull();
	});
});

describe('SettingsOverview', () => {
	it('points at the next step and maps every section', async () => {
		render(<SettingsOverview connectionsEnvManaged={false} />);
		const setup = await screen.findByRole('region', { name: '接入向导' });
		expect(await within(setup).findByText('已完成 2 / 4')).toBeTruthy();
		const next = within(setup).getByRole('link', { name: /下一步/ });
		expect(next.getAttribute('href')).toBe('/settings/object-types');

		const map = screen.getByRole('region', { name: '全部功能' });
		expect(
			within(map)
				.getByRole('link', { name: /使用统计/ })
				.getAttribute('href'),
		).toBe('/settings/usage');
		expect(screen.getByRole('region', { name: '管理待办' })).toBeTruthy();
	});
});
