// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';

/** The fields a policy refusal names: ``你没有权限查看以下字段：a.b、c.d（…）``. */
const DENIED = /你没有权限查看以下字段：([^（\n。]+)/;

export const deniedFields = (content: string): string[] => {
	const match = DENIED.exec(content);
	if (!match) return [];
	return match[1]
		.split('、')
		.map((f) => f.trim())
		.filter(Boolean);
};

/** Below a refused answer: one link per field, to request access to it. */
export const AccessDeniedHint = ({ content, question }: { content: string; question?: string }) => {
	const fields = deniedFields(content);
	if (fields.length === 0) return null;
	return (
		<div className="mt-3 flex flex-wrap items-center gap-2 border-t border-zinc-200 pt-3 text-xs dark:border-zinc-700">
			<span className="text-secondary dark:text-zinc-400">需要这些数据？</span>
			{fields.map((field) => {
				const params = new URLSearchParams({ field });
				if (question) params.set('question', question);
				return (
					<Link
						key={field}
						href={`/account/access-requests?${params.toString()}`}
						className="rounded-md border border-[#2563eb]/40 bg-white px-2 py-1 text-[#1e40af] hover:bg-[#2563eb]/10 dark:bg-zinc-900 dark:text-[#60a5fa]"
					>
						申请访问 {field}
					</Link>
				);
			})}
		</div>
	);
};
