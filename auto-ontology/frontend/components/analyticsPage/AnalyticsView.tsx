// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';

import { Button } from '@/common/Button';
import { EmptyState } from '@/common/EmptyState';
import { Size, ButtonTheme } from '@/enums/button';
import { ToastVariant } from '@/enums/toast';
import { Icon, IconName } from '@/common/icons';
import { SkeletonTable } from '@/common/Skeleton';
import { Table } from '@/common/Table';
import { Toast } from '@/common/Toast';
import { analyticsApi } from '@/api/analytics';
import { formatDate } from '@/common/date';
import { usePagination } from '@/hooks/usePagination';
import type { ConversationAnalytics } from '@/types/analytics';
import type { TableColumn } from '@/types/table';

const CSV_HEADERS = ['Timestamp', 'User', 'Source', 'Question', 'Reasoning', 'SQL'];
const escapeCsv = (value: string) => `"${value.replace(/"/g, '""')}"`;

const COLUMNS: TableColumn<ConversationAnalytics>[] = [
	{
		key: 'question_timestamp',
		header: '时间',
		width: 'w-44',
		nowrap: true,
		className: 'text-body dark:text-zinc-300',
		cell: (row) => formatDate(row.question_timestamp),
	},
	{
		key: 'user',
		header: '用户',
		width: 'w-40',
		nowrap: true,
		truncate: true,
		className: 'text-body dark:text-zinc-300',
		cell: (row) => row.user.name || row.user.email,
		title: (row) => row.user.name || row.user.email,
	},
	{
		key: 'source',
		header: '来源',
		width: 'w-24',
		nowrap: true,
		className: 'text-body dark:text-zinc-300 uppercase',
		cell: (row) => row.source ?? '—',
		title: (row) => row.source ?? '',
	},
	{
		key: 'question',
		header: '问题',
		truncate: true,
		className: 'text-body dark:text-zinc-300',
		cell: (row) => row.question,
		title: (row) => row.question ?? '',
	},
	{
		key: 'response',
		header: '推理过程',
		truncate: true,
		className: 'text-body dark:text-zinc-300',
		cell: (row) => row.response,
		title: (row) => row.response ?? '',
	},
	{
		key: 'sql',
		header: 'SQL',
		truncate: true,
		cell: (row) => row.sql,
		title: (row) => row.sql ?? '',
	},
];

export const AnalyticsView = () => {
	const [rows, setRows] = useState<ConversationAnalytics[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [downloading, setDownloading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	// Kept apart from `error`: the table below only renders while `error` is
	// null, so a failed export must not take the rows already on screen with it.
	const [downloadError, setDownloadError] = useState<string | null>(null);
	const { skip, pageSize, pagination } = usePagination({ totalItems: total });

	useEffect(() => {
		let cancelled = false;

		(async () => {
			setLoading(true);
			const res = await analyticsApi.list({ skip, limit: pageSize });
			if (cancelled) return;
			if (res.error) {
				// The page already on screen is left alone: dropping the total
				// would collapse the pager to page one and send the request for
				// it, so a single failed request would cost two.
				setError(res.message ?? '加载统计数据失败');
			} else {
				setError(null);
				setRows(res.data ?? []);
				setTotal(res.total);
			}
			setLoading(false);
		})();

		return () => {
			cancelled = true;
		};
	}, [skip, pageSize]);

	const downloadRows = (analytics: ConversationAnalytics[]) => {
		const lines = [
			CSV_HEADERS.join(','),
			...analytics.map((row) =>
				[
					formatDate(row.question_timestamp),
					row.user.name || row.user.email,
					row.source ?? '',
					row.question ?? '',
					row.response ?? '',
					row.sql ?? '',
				]
					.map(escapeCsv)
					.join(','),
			),
		];
		const csv = lines.join('\r\n');

		const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const filename = `auto-ontology-analytics-${formatDate(Date.now(), 'YYYY-MM')}.csv`;
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = filename;
		document.body.appendChild(anchor);
		anchor.click();
		anchor.remove();
		URL.revokeObjectURL(url);
	};

	const handleDownload = async () => {
		setDownloading(true);
		setDownloadError(null);
		const res = await analyticsApi.list();
		setDownloading(false);
		if (res.error) {
			setDownloadError(res.message ?? '下载统计数据失败');
			return;
		}
		downloadRows(res.data ?? []);
	};

	return (
		<div className="flex h-full w-full flex-col bg-white dark:bg-zinc-950">
			<header className="flex items-center gap-3 border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
				<Icon name={IconName.ChartLine} className="h-5 w-5 text-body dark:text-zinc-300" />
				<h1 className="text-lg font-semibold tracking-tight text-heading dark:text-zinc-100">
					使用统计
				</h1>
				<div className="ml-auto">
					<Button
						theme={ButtonTheme.Primary}
						size={Size.REGULAR}
						type="button"
						onClick={handleDownload}
						disabled={total === 0 || downloading}
						shadow
					>
						{downloading ? '正在准备下载…' : '下载'}
					</Button>
				</div>
			</header>

			<div className="flex-1 overflow-y-auto px-6 py-6">
				{loading && (
					<div role="status" aria-label="正在加载统计数据">
						<SkeletonTable columns={6} rows={10} />
					</div>
				)}

				{!loading && error == null && total === 0 && (
					<EmptyState
						icon={IconName.ChartLine}
						title="还没有统计记录"
						description="在对话中发送消息时会自动记录统计数据。"
					/>
				)}

				{!loading && error == null && rows.length > 0 && (
					<Table
						columns={COLUMNS}
						rows={rows}
						rowKey={(row) => row.id}
						pagination={pagination}
					/>
				)}
			</div>

			<Toast
				open={error !== null}
				message={error ?? ''}
				title="无法加载统计数据"
				variant={ToastVariant.Error}
				onClose={() => setError(null)}
			/>

			<Toast
				open={downloadError !== null}
				message={downloadError ?? ''}
				title="无法下载统计数据"
				variant={ToastVariant.Error}
				onClose={() => setDownloadError(null)}
			/>
		</div>
	);
};
