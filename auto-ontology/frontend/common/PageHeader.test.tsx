// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IconName } from '@/common/icons';
import { PageHeader } from './PageHeader';

describe('PageHeader', () => {
	it('names the page as its only heading, with what it is for', () => {
		render(
			<PageHeader
				title="业务对象"
				description="按业务对象查看数据"
				icon={IconName.Cube}
				actions={<button type="button">新建</button>}
			/>,
		);
		expect(screen.getByRole('heading', { level: 1, name: '业务对象' })).toBeTruthy();
		expect(screen.getByText('按业务对象查看数据')).toBeTruthy();
		expect(screen.getByRole('button', { name: '新建' })).toBeTruthy();
	});

	it('renders without the optional parts', () => {
		const { container } = render(<PageHeader title="首页" />);
		expect(container.querySelectorAll('p')).toHaveLength(0);
	});
});
