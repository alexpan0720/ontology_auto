// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { navigation, nextLinkMock, nextNavigationMock, resetNavigation } from '@/test/nextMocks';
import { NavRail, SIDEBAR_COLLAPSED_KEY } from './NavRail';

vi.mock('next/navigation', () => nextNavigationMock());
vi.mock('next/link', () => nextLinkMock());

describe('NavRail', () => {
	beforeEach(() => resetNavigation('/objects'));

	it('labels every destination and marks the current one', () => {
		render(<NavRail />);
		const current = screen.getByRole('link', { name: '业务对象' });
		expect(current.getAttribute('aria-current')).toBe('page');
		expect(screen.getByRole('link', { name: '问数' }).getAttribute('aria-current')).toBeNull();
		expect(screen.getByText('数据资产')).toBeTruthy();
	});

	it('hides administration from a viewer', () => {
		render(<NavRail />);
		expect(screen.queryByRole('link', { name: '管理中心' })).toBeNull();
	});

	it('shows administration to an admin', () => {
		navigation.pathname = '/settings/users';
		render(<NavRail isAdmin />);
		const settings = screen.getByRole('link', { name: '管理中心' });
		expect(settings.getAttribute('aria-current')).toBe('page');
	});

	it('collapses to icons and remembers the choice', () => {
		render(<NavRail />);
		fireEvent.click(screen.getByRole('button', { name: '收起侧边栏' }));
		expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe('1');
		expect(screen.queryByText('业务对象')).toBeNull();
		expect(screen.getByTitle('业务对象')).toBeTruthy();
		expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeTruthy();
	});

	it('starts collapsed when the browser remembers it so', () => {
		window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, '1');
		render(<NavRail />);
		expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeTruthy();
	});
});
