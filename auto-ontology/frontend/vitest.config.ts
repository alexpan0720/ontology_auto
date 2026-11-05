// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const root = fileURLToPath(new URL('.', import.meta.url));

// Component tests run in jsdom. SVG icons are SVGR components in the app; here
// they resolve to a stub so a test can find an icon by its file name.
export default defineConfig({
	resolve: {
		alias: [
			{ find: /^.+\.svg$/, replacement: `${root}test/svgStub.tsx` },
			{ find: /^@\//, replacement: root },
		],
	},
	oxc: { jsx: { runtime: 'automatic' } },
	test: {
		environment: 'jsdom',
		include: ['**/*.test.{ts,tsx}'],
		exclude: ['node_modules/**', '.next/**'],
		setupFiles: ['test/setup.ts'],
	},
});
