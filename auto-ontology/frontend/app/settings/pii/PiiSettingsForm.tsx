// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState } from 'react';
import { piiDetectionApi } from '@/api/settings';
import { Toast } from '@/common/Toast';
import { Toggle } from '@/common/Toggle';
import { ToastVariant } from '@/enums/toast';

export const PiiSettingsForm = ({ initialEnabled }: { initialEnabled: boolean }) => {
	// Seeded from the server (see page.tsx) so the correct state renders on first
	// paint; updated optimistically and rolled back if the save fails.
	const [enabled, setEnabled] = useState(initialEnabled);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [message, setMessage] = useState<string | null>(null);

	const handleToggle = async (next: boolean) => {
		if (saving || next === enabled) return;
		setSaving(true);
		setError(null);
		setMessage(null);
		setEnabled(next);

		try {
			const result = await piiDetectionApi.setEnabled(next);
			setEnabled(result.enabled);
			setMessage(
				result.enabled
					? '已开启敏感信息检测，下次导入时生效。'
					: '已关闭敏感信息检测，导入时将跳过敏感信息分类。',
			);
		} catch {
			setEnabled(!next); // roll back the optimistic update
			setError('更新敏感信息检测设置失败，请重试。');
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="h-full overflow-auto p-6">
			<div className="mx-auto max-w-xl">
				<h1 className="mb-1 text-lg font-semibold text-heading dark:text-zinc-100">
					敏感信息设置
				</h1>
				<p className="mb-4 text-xs text-secondary">
					开启后，导入时会对目录中的列进行分类，并添加统一的敏感信息（PII）标签。
					关闭则跳过这一步，已有的标签会保留。
				</p>

				<div className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
					<div className="flex flex-col pr-4">
						<span className="text-sm font-medium text-heading dark:text-zinc-100">
							敏感信息检测
						</span>
						<span className="text-xs text-secondary">
							{enabled
								? '开启 —— 导入时对列进行分类并标记敏感信息。'
								: '关闭 —— 导入时跳过敏感信息分类。'}
						</span>
					</div>
					<Toggle
						checked={enabled}
						aria-label="敏感信息检测"
						disabled={saving}
						onChange={handleToggle}
					/>
				</div>
			</div>

			<Toast
				open={error !== null}
				message={error ?? ''}
				variant={ToastVariant.Error}
				onClose={() => setError(null)}
			/>
			<Toast
				open={message !== null}
				message={message ?? ''}
				variant={ToastVariant.Success}
				onClose={() => setMessage(null)}
			/>
		</div>
	);
};
