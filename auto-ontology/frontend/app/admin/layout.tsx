// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const tabs = [
	{ href: '/admin/users', label: '用户' },
	{ href: '/admin/sso', label: '单点登录' },
];

const AdminLayout = ({ children }: { children: React.ReactNode }) => {
	const pathname = usePathname();

	return (
		<div className="flex h-full flex-col">
			<div className="flex gap-1 border-b border-zinc-200 px-6 pt-3 dark:border-zinc-800">
				{tabs.map((tab) => {
					const active = pathname.startsWith(tab.href);
					return (
						<Link
							key={tab.href}
							href={tab.href}
							className={`rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
								active
									? 'border-[#2563eb] text-[#2563eb]'
									: 'border-transparent text-secondary hover:text-body dark:hover:text-zinc-300'
							}`}
						>
							{tab.label}
						</Link>
					);
				})}
			</div>
			<div className="min-h-0 flex-1">{children}</div>
		</div>
	);
};

export default AdminLayout;
