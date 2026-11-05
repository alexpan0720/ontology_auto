// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';
import { NAV_SECTIONS, isNavItemActive, navItem, visibleNavSections } from './navigation';

const keys = (isAdmin: boolean) =>
	visibleNavSections(isAdmin).flatMap((section) => section.items.map((item) => item.key));

describe('navigation', () => {
	it('shows a viewer the business pages and data assets, not administration', () => {
		expect(keys(false)).toEqual([
			'home',
			'chat',
			'objects',
			'terms',
			'data',
			'exploration',
			'analysis',
		]);
	});

	it('adds the admin centre for an admin', () => {
		expect(keys(true)).toContain('settings');
	});

	it('gives every item a unique key and href', () => {
		const items = NAV_SECTIONS.flatMap((section) => section.items);
		expect(new Set(items.map((item) => item.key)).size).toBe(items.length);
		expect(new Set(items.map((item) => item.href)).size).toBe(items.length);
	});

	it('marks an item active on its own pages and the routes folded into it', () => {
		expect(isNavItemActive('/objects', navItem('objects'))).toBe(true);
		expect(isNavItemActive('/settings/users', navItem('settings'))).toBe(true);
		expect(isNavItemActive('/discovery', navItem('data'))).toBe(true);
		expect(isNavItemActive('/analytics', navItem('settings'))).toBe(true);
	});

	it('does not mistake a shared prefix for a sub-page', () => {
		expect(isNavItemActive('/chatroom', navItem('chat'))).toBe(false);
		expect(isNavItemActive('/home', navItem('chat'))).toBe(false);
	});

	it('refuses an unknown key', () => {
		expect(() => navItem('nope')).toThrow();
	});
});
