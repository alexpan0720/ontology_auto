// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SETTINGS_GROUPS, isSettingsHrefActive, visibleSettingsGroups } from './settingsNavigation';

const hrefs = (groups = SETTINGS_GROUPS) =>
	groups.flatMap((group) => group.items.map((item) => item.href));

describe('settings navigation', () => {
	it('lists every settings page exactly once', () => {
		// Each page directory under app/settings must be reachable from the menu,
		// so a new page cannot be added and forgotten there.
		const root = join(__dirname, '..', 'app', 'settings');
		const pages = readdirSync(root)
			.filter((name) => statSync(join(root, name)).isDirectory())
			.map((name) => `/settings/${name}`)
			.sort();
		expect([...hrefs()].sort()).toEqual(pages);
		expect(new Set(hrefs()).size).toBe(hrefs().length);
	});

	it('describes every item for the overview', () => {
		for (const item of SETTINGS_GROUPS.flatMap((group) => group.items)) {
			expect(item.description.length).toBeGreaterThan(0);
		}
	});

	it('drops connections when they come from the environment', () => {
		expect(hrefs(visibleSettingsGroups(true))).not.toContain('/settings/connections');
		expect(hrefs(visibleSettingsGroups(false))).toContain('/settings/connections');
	});

	it('selects the overview only on itself', () => {
		expect(isSettingsHrefActive('/settings', '/settings')).toBe(true);
		expect(isSettingsHrefActive('/settings/users', '/settings')).toBe(false);
		expect(isSettingsHrefActive('/settings/users/groups', '/settings/users')).toBe(true);
		expect(isSettingsHrefActive('/settings/usage', '/settings/users')).toBe(false);
	});
});
