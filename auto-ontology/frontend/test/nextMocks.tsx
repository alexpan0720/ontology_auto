// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { AnchorHTMLAttributes, ReactNode } from 'react';
import { vi } from 'vitest';

/**
 * What the Next.js router modules resolve to under test. A test sets
 * `navigation.pathname` / `navigation.search` and reads `navigation.push`.
 */
export const navigation = {
	pathname: '/',
	search: '',
	push: vi.fn(),
	replace: vi.fn(),
};

export const resetNavigation = (pathname = '/', search = ''): void => {
	navigation.pathname = pathname;
	navigation.search = search;
	navigation.push.mockReset();
	navigation.replace.mockReset();
};

export const nextNavigationMock = () => ({
	usePathname: () => navigation.pathname,
	useSearchParams: () => new URLSearchParams(navigation.search),
	useRouter: () => ({
		push: navigation.push,
		replace: navigation.replace,
		refresh: vi.fn(),
		back: vi.fn(),
		prefetch: vi.fn(),
	}),
	redirect: vi.fn(),
});

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; children?: ReactNode };

export const nextLinkMock = () => ({
	default: ({ href, children, ...rest }: LinkProps) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
});
