// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import { distinctValueProbingApi, semanticCompilationApi } from '@/api/settings';
import { formatDate } from '@/common/date';
import { Icon, IconName } from '@/common/icons';
import { ConfirmModal } from '@/common/modal';
import { Spinner } from '@/common/Spinner';
import { Toast } from '@/common/Toast';
import { Toggle } from '@/common/Toggle';
import { ToastVariant } from '@/enums/toast';

export const SemanticCompilationForm = ({
	initialEnabled,
	initialProbingEnabled,
	hasDatabases,
}: {
	initialEnabled: boolean;
	initialProbingEnabled: boolean;
	hasDatabases: boolean;
}) => {
	// Seeded from the server (see page.tsx) so the correct state renders on first
	// paint; updated optimistically and rolled back if the save fails.
	const [enabled, setEnabled] = useState(initialEnabled);
	const [probingEnabled, setProbingEnabled] = useState(initialProbingEnabled);
	const [savingProbing, setSavingProbing] = useState(false);
	const [saving, setSaving] = useState(false);
	const [confirmModalOpen, setConfirmModalOpen] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [message, setMessage] = useState<string | null>(null);
	const [running, setRunning] = useState(false);
	const [lastSuccessAt, setLastSuccessAt] = useState<string | null>(null);
	const [lastFailureAt, setLastFailureAt] = useState<string | null>(null);
	useEffect(() => {
		semanticCompilationApi
			.getStatus()
			.then((result) => {
				setRunning(result.running);
				setLastSuccessAt(result.last_success_at);
				setLastFailureAt(result.last_failure_at);
			})
			.catch(() => {});
	}, []);
	// Only set when it's more recent than the last success (see history.py),
	// so a stale failure never outlives the run that fixed it.
	const failed = !running && lastFailureAt !== null;
	// Whether semantic_compilation_history has anything to report yet. A newly
	// enabled instance that hasn't finished its first pass has none of these,
	// so there's nothing meaningful to show — surfacing "ready" with a "—"
	// placeholder would be misleading.
	const hasHistory = running || lastSuccessAt !== null || lastFailureAt !== null;

	const handleToggle = async () => {
		if (saving) return;
		const next = !enabled;
		setSaving(true);
		setError(null);
		setMessage(null);
		setEnabled(next);

		try {
			const result = await semanticCompilationApi.setEnabled(next);
			setEnabled(result.enabled);
			setMessage(result.enabled ? '已启用语义编译，并已触发一次编译。' : '已关闭语义编译。');
			if (result.enabled) {
				// Enabling triggers a run immediately (see the PUT route), so by the
				// time this resolves the ingestion service has already inserted a
				// history row and is very likely already running — refresh status
				// so the section appears now instead of only on the next page load.
				semanticCompilationApi
					.getStatus()
					.then((status) => {
						setRunning(status.running);
						setLastSuccessAt(status.last_success_at);
						setLastFailureAt(status.last_failure_at);
					})
					.catch(() => {});
			}
		} catch {
			setEnabled(!next); // roll back the optimistic update
			setError('更新语义编译设置失败，请重试。');
		} finally {
			setSaving(false);
		}
	};

	const handleProbingToggle = async () => {
		if (savingProbing) return;
		const next = !probingEnabled;
		setSavingProbing(true);
		setError(null);
		setMessage(null);
		setProbingEnabled(next);

		try {
			const result = await distinctValueProbingApi.setEnabled(next);
			setProbingEnabled(result.enabled);
			// No run is triggered: the flag is read at the start of each run, so
			// say when it takes effect rather than implying something happened now.
			setMessage(
				result.enabled
					? '已开启取值全量扫描，下次编译时生效。'
					: '已关闭取值全量扫描，下次编译时生效。',
			);
		} catch {
			setProbingEnabled(!next); // roll back the optimistic update
			setError('更新取值全量扫描设置失败，请重试。');
		} finally {
			setSavingProbing(false);
		}
	};

	const handleReset = () => {
		setError(null);
		setConfirmModalOpen(false);
		// The ingestion service deletes in the background and answers 202, so the
		// request only starts the reset. Nothing here depends on the response, so
		// it is left unawaited and only a failure to reach the API is surfaced.
		setMessage('已开始重置语义层，将在后台运行。');
		semanticCompilationApi.reset().catch(() => {
			setMessage(null);
			setError('重置语义层失败，请重试。');
		});
	};

	return (
		<div className="h-full overflow-auto p-6">
			<div className="mx-auto max-w-xl">
				<h1 className="mb-1 text-lg font-semibold text-heading dark:text-zinc-100">
					语义编译
				</h1>
				<p className="mb-4 text-xs text-secondary">
					开启后，数据导入服务会在启动时以及每 24
					小时为所有已连接的数据库编译一次语义层。开启时也会立即触发一次编译。
				</p>

				{!hasDatabases && (
					<div className="mb-3 flex items-center rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
						<span className="text-sm font-medium text-heading dark:text-zinc-100">
							请先连接一个数据源
						</span>
					</div>
				)}

				{hasDatabases && (
					<>
						{enabled && hasHistory && (
							<div className="mb-3 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
								<div className="flex flex-col">
									<span className="text-sm font-medium text-heading dark:text-zinc-100">
										{running && '语义编译进行中'}
										{!running && failed && '语义编译失败'}
										{!running && !failed && '语义编译已完成'}
									</span>
									<span className="text-xs text-secondary">
										{failed && !running
											? `最近一次尝试：${formatDate(lastFailureAt as string, 'MMM DD YYYY, HH:mm Z')}`
											: `最近一次语义编译：${
													lastSuccessAt
														? formatDate(
																lastSuccessAt,
																'MMM DD YYYY, HH:mm Z',
															)
														: '—'
												}`}
									</span>
								</div>
								{running ? (
									<span title="语义编译进行中">
										<Spinner className="h-4 w-4 shrink-0 text-[#2563eb]" />
									</span>
								) : failed ? (
									<span
										className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-red-600 dark:text-red-400"
										title="语义编译失败"
									>
										<Icon name={IconName.Close} className="h-3 w-3" />
									</span>
								) : (
									<span
										className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#2563eb]/15 text-[#2563eb]"
										title="语义编译已完成"
									>
										<Icon name={IconName.Check} className="h-3 w-3" />
									</span>
								)}
							</div>
						)}

						{!enabled && (
							<div className="mb-3 flex items-center rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
								<span className="text-sm font-medium text-heading dark:text-zinc-100">
									可以启用语义编译
								</span>
							</div>
						)}

						{/* Above the compilation toggle on purpose: this is a property of
						    how compilation runs, so it can be set before turning
						    compilation on, and stays editable afterwards. */}
						<div className="mb-3 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
							<div className="flex flex-col pr-4">
								<span className="text-sm font-medium text-heading dark:text-zinc-100">
									取值全量扫描
								</span>
								<span className="text-xs text-secondary">
									{probingEnabled
										? '扫描低基数文本列的全部取值，确保少见的类别也能被识别。'
										: '关闭 —— 列只保留在各表抽样行中出现过的取值。'}
								</span>
							</div>
							<Toggle
								checked={probingEnabled}
								aria-label="取值全量扫描"
								disabled={savingProbing}
								onChange={handleProbingToggle}
							/>
						</div>

						<div className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
							<div className="flex flex-col">
								<span className="text-sm font-medium text-heading dark:text-zinc-100">
									启用语义编译
								</span>
								<span className="text-xs text-secondary">
									{enabled ? '按每 24 小时一次的计划运行。' : '当前已关闭。'}
								</span>
							</div>
							<Toggle
								checked={enabled}
								aria-label="启用语义编译"
								disabled={saving}
								onChange={handleToggle}
							/>
						</div>

						{enabled && (
							<div className="mt-3 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
								<div className="flex flex-col">
									<span className="text-sm font-medium text-heading dark:text-zinc-100">
										重置语义层
									</span>
									<span className="text-xs text-secondary">
										删除所有数据库的语义层，并从头重建。
									</span>
								</div>
								<button
									type="button"
									disabled={saving}
									onClick={() => setConfirmModalOpen(true)}
									className="cursor-pointer rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/40"
								>
									重置
								</button>
							</div>
						)}
					</>
				)}
			</div>

			<ConfirmModal
				open={confirmModalOpen}
				title="重置语义层"
				message="这会删除语义层，并触发重新构建。"
				confirmLabel="重置"
				onConfirm={handleReset}
				onCancel={() => setConfirmModalOpen(false)}
			/>

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
