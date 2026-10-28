// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import { datasources } from '@/api/datasources';
import { modelInterchangeApi } from '@/api/modelInterchange';
import { Button } from '@/common/Button';
import { FileUpload } from '@/common/FileUpload';
import { Icon, IconName } from '@/common/icons';
import { ConfirmModal } from '@/common/modal';
import { ProgressBar } from '@/common/ProgressBar';
import { SkeletonRows } from '@/common/Skeleton';
import { Toast } from '@/common/Toast';
import { Toggle } from '@/common/Toggle';
import { ButtonTheme, Size } from '@/enums/button';
import { ModelFormat } from '@/enums/modelInterchange';
import { ToastVariant } from '@/enums/toast';
import { useSmoothProgress } from '@/lib/useSmoothProgress';
import type { Database } from '@/types/datasources';
import type { ImportEntityCounts, ImportSummary } from '@/types/modelInterchange';

const FORMAT_LABEL: Record<ModelFormat, string> = {
	[ModelFormat.AUTO_ONTOLOGY]: 'alexpan 本体 原生格式',
	[ModelFormat.OSSIE]: 'Apache Ossie',
};

const EXPORT_FILENAME: Record<ModelFormat, string> = {
	[ModelFormat.AUTO_ONTOLOGY]: 'auto-ontology-model.yaml',
	[ModelFormat.OSSIE]: 'ossie-model.yaml',
};

// The Ossie semantic model, ontology and mapping, which are separate documents.
const OSSIE_WITH_ONTOLOGY_FILENAME = 'ossie-model.zip';

const FORMAT_OPTIONS: { value: ModelFormat; description: string }[] = [
	{
		value: ModelFormat.AUTO_ONTOLOGY,
		description: 'alexpan 本体 存储的全部内容，包括 Ossie 无法表示的目录对象。',
	},
	{
		value: ModelFormat.OSSIE,
		description: '开放语义交换（OSI）模型，可在其他 Ossie 工具中使用。',
	},
];

const downloadBlob = (blob: Blob, filename: string) => {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	document.body.appendChild(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
};

const createdCountEntries = (counts: ImportEntityCounts): [string, number][] =>
	Object.entries(counts).filter(([, value]) => value > 0);

const checkboxClassName = 'h-4 w-4 rounded border-zinc-300 text-[#2563eb] focus:ring-[#2563eb]/30';

const radioClassName = 'mt-0.5 h-4 w-4 border-zinc-300 text-[#2563eb] focus:ring-[#2563eb]/30';

const isYamlFile = (file: File): boolean => /\.ya?ml$/i.test(file.name);

const validateYamlFile = (file: File): string | null =>
	isYamlFile(file) ? null : '请选择 .yaml 或 .yml 文件。';

export const ImportExportView = () => {
	const [databases, setDatabases] = useState<Database[]>([]);
	const [databasesLoading, setDatabasesLoading] = useState(true);
	const [databasesError, setDatabasesError] = useState<string | null>(null);
	const [selectedDbIds, setSelectedDbIds] = useState<Set<string>>(new Set());

	const [exportFormat, setExportFormat] = useState<ModelFormat>(ModelFormat.AUTO_ONTOLOGY);
	const [includeOntology, setIncludeOntology] = useState(true);
	const [exporting, setExporting] = useState(false);
	const [exportError, setExportError] = useState<string | null>(null);
	const [exportMessage, setExportMessage] = useState<string | null>(null);
	const exportProgress = useSmoothProgress();

	const [importFile, setImportFile] = useState<File | null>(null);
	const [replace, setReplace] = useState(true);
	const [embed, setEmbed] = useState(true);
	const [confirmImportOpen, setConfirmImportOpen] = useState(false);
	const [importing, setImporting] = useState(false);
	const [importError, setImportError] = useState<string | null>(null);
	const [importSummary, setImportSummary] = useState<ImportSummary | null>(null);

	useEffect(() => {
		let active = true;
		void (async () => {
			setDatabasesLoading(true);
			const res = await datasources.getDBs();
			if (!active) return;
			if (res.error) {
				setDatabasesError(res.message ?? '加载数据库失败。');
				setDatabases([]);
			} else {
				const data = res.data ?? [];
				setDatabasesError(null);
				setDatabases(data);
				// Default to exporting everything.
				setSelectedDbIds(new Set(data.map((db) => db.id)));
			}
			setDatabasesLoading(false);
		})();
		return () => {
			active = false;
		};
	}, []);

	const allSelected = databases.length > 0 && selectedDbIds.size === databases.length;

	const toggleDatabase = (id: string) => {
		setSelectedDbIds((prev) => {
			const next = new Set(prev);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	};

	const toggleSelectAll = () => {
		setSelectedDbIds(allSelected ? new Set() : new Set(databases.map((db) => db.id)));
	};

	const handleExport = async () => {
		if (selectedDbIds.size === 0 || exporting) return;
		const withOntology = exportFormat === ModelFormat.OSSIE && includeOntology;
		setExporting(true);
		setExportError(null);
		// The YAML arrives in one response, so this eases toward 90% while we
		// wait, then `complete()` snaps to 100% when the file is ready.
		exportProgress.start({
			tauMs:
				2200 + selectedDbIds.size * 450 + (exportFormat === ModelFormat.OSSIE ? 1200 : 0),
		});
		try {
			const res = await modelInterchangeApi.exportModel(
				Array.from(selectedDbIds),
				exportFormat,
				withOntology,
			);
			if (res.error) {
				exportProgress.fail();
				setExportError(res.message ?? '导出模型失败。');
				return;
			}
			await exportProgress.complete();
			downloadBlob(
				res.blob,
				withOntology ? OSSIE_WITH_ONTOLOGY_FILENAME : EXPORT_FILENAME[exportFormat],
			);
			setExportMessage(
				withOntology
					? `模型已导出为 ${FORMAT_LABEL[exportFormat]} 格式，并包含本体与映射。`
					: `模型已导出为 ${FORMAT_LABEL[exportFormat]} 格式。`,
			);
		} catch {
			exportProgress.fail();
			setExportError('导出模型失败。');
		} finally {
			setExporting(false);
		}
	};

	const handleImportFileChange = (file: File | null) => {
		setImportFile(file);
		setImportError(null);
		setImportSummary(null);
	};

	const handleRequestImport = () => {
		if (!importFile || importing) return;
		setImportError(null);
		setConfirmImportOpen(true);
	};

	const handleCancelImport = () => {
		if (importing) return;
		setConfirmImportOpen(false);
	};

	const handleConfirmImport = async () => {
		if (!importFile) return;
		setImporting(true);
		setImportError(null);
		const res = await modelInterchangeApi.importModel(importFile, { replace, embed });
		setImporting(false);

		if (res.error) {
			setImportError(res.message ?? '导入模型失败。');
			return;
		}

		setImportSummary(res.summary);
		setConfirmImportOpen(false);
		setImportFile(null);
	};

	return (
		<div className="mx-auto w-full max-w-2xl space-y-6">
			<h1 className="text-lg font-semibold text-heading dark:text-zinc-100">导入 / 导出</h1>

			<section className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-700">
				<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">导出模型</h2>
				<p className="mt-1 text-xs text-secondary">
					将所选数据库的目录和语义层下载为 YAML 文件；包含 Ossie 本体时下载为 .zip 文件。
				</p>

				<fieldset className="mt-4">
					<legend className="text-xs font-medium text-heading dark:text-zinc-200">
						格式
					</legend>
					<div className="mt-2 grid gap-2 sm:grid-cols-2">
						{FORMAT_OPTIONS.map(({ value, description }) => (
							<label
								key={value}
								className="flex cursor-pointer items-start gap-2 rounded-lg border border-zinc-200 px-3 py-2 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800/80"
							>
								<input
									type="radio"
									name="export-format"
									value={value}
									checked={exportFormat === value}
									onChange={() => setExportFormat(value)}
									className={radioClassName}
								/>
								<span>
									<span className="block text-sm font-medium text-heading dark:text-zinc-100">
										{FORMAT_LABEL[value]}
									</span>
									<span className="block text-xs text-secondary">
										{description}
									</span>
								</span>
							</label>
						))}
					</div>
				</fieldset>

				{exportFormat === ModelFormat.OSSIE ? (
					<div className="mt-3 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
						<div className="flex flex-col">
							<span className="text-sm font-medium text-heading dark:text-zinc-100">
								包含本体与映射
							</span>
							<span className="text-xs text-secondary">
								同时将术语导出为 Ossie
								本体，并附带到语义模型的映射，打包为包含三个文件的 .zip。
							</span>
						</div>
						<Toggle
							checked={includeOntology}
							aria-label="包含本体与映射"
							onChange={setIncludeOntology}
						/>
					</div>
				) : null}

				{databasesLoading ? (
					<div className="mt-4">
						<SkeletonRows rows={3} />
					</div>
				) : databasesError ? (
					<p className="mt-4 text-sm text-red-600 dark:text-red-400">{databasesError}</p>
				) : databases.length === 0 ? (
					<p className="mt-4 text-sm text-secondary">未找到数据库。</p>
				) : (
					<div className="mt-4 space-y-2">
						<label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/80">
							<input
								type="checkbox"
								checked={allSelected}
								onChange={toggleSelectAll}
								className={checkboxClassName}
							/>
							<span className="text-sm font-medium text-heading dark:text-zinc-200">
								{allSelected ? '取消全选' : '全选'}
							</span>
						</label>
						<div className="max-h-56 overflow-y-auto rounded-md border border-zinc-100 dark:border-zinc-800">
							{databases.map((db) => (
								<label
									key={db.id}
									className="flex cursor-pointer items-center gap-3 border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/80"
								>
									<input
										type="checkbox"
										checked={selectedDbIds.has(db.id)}
										onChange={() => toggleDatabase(db.id)}
										className={checkboxClassName}
									/>
									<span className="text-sm text-heading dark:text-zinc-200">
										{db.name}
									</span>
								</label>
							))}
						</div>
					</div>
				)}

				{exportError ? (
					<p className="mt-3 text-sm text-red-600 dark:text-red-400">{exportError}</p>
				) : null}

				{exporting ? (
					<ProgressBar
						value={exportProgress.value}
						showValue
						label="正在导出"
						className="mt-4"
						aria-label={`正在导出模型，已完成 ${Math.round(exportProgress.value)}%`}
					/>
				) : null}

				<div className="mt-4 flex justify-end">
					<Button
						theme={ButtonTheme.Primary}
						size={Size.REGULAR}
						type="button"
						onClick={() => {
							void handleExport();
						}}
						disabled={selectedDbIds.size === 0 || exporting || databasesLoading}
						loading={exporting}
						iconPosition="left"
					>
						<Icon name={IconName.Download} className="h-4 w-4" />
						{exporting ? '导出中…' : '导出'}
					</Button>
				</div>
			</section>

			<section className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-700">
				<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">导入模型</h2>
				<p className="mt-1 text-xs text-secondary">
					上传 alexpan 本体 原生格式或 Apache Ossie 模型的 YAML
					文件，写入目录和语义层。文件格式会自动识别。
				</p>

				<FileUpload
					value={importFile}
					onChange={handleImportFileChange}
					onError={setImportError}
					validate={validateYamlFile}
					accept=".yaml,.yml"
					description="YAML 文件（.yaml、.yml）"
					aria-label="上传 alexpan 本体 或 Apache Ossie 模型的 YAML 文件"
					className="mt-4"
				/>

				{importError && !confirmImportOpen ? (
					<p className="mt-2 text-sm text-red-600 dark:text-red-400">{importError}</p>
				) : null}

				<div className="mt-4 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
					<div className="flex flex-col">
						<span className="text-sm font-medium text-heading dark:text-zinc-100">
							替换现有数据
						</span>
						<span className="text-xs text-secondary">
							删除已导入数据库中、此文件里没有的语义层数据。
						</span>
					</div>
					<Toggle checked={replace} aria-label="替换现有数据" onChange={setReplace} />
				</div>

				<div className="mt-3 flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 dark:border-zinc-700">
					<div className="flex flex-col">
						<span className="text-sm font-medium text-heading dark:text-zinc-100">
							重新生成向量
						</span>
						<span className="text-xs text-secondary">
							为新建的节点生成向量并写入向量数据库。
						</span>
					</div>
					<Toggle checked={embed} aria-label="重新生成向量" onChange={setEmbed} />
				</div>

				{importSummary ? (
					<div className="mt-3 rounded-lg border border-[#2563eb]/30 bg-[#2563eb]/5 p-3 text-xs text-body dark:text-zinc-300">
						<p className="font-medium text-heading dark:text-zinc-100">导入摘要</p>
						<ul className="mt-1.5 space-y-0.5">
							<li>识别为 {FORMAT_LABEL[importSummary.format]}</li>
							{createdCountEntries(importSummary.created).map(([key, value]) => (
								<li key={key}>
									Created {value} {key.replace(/_/g, ' ')}
								</li>
							))}
							{importSummary.embeddings ? (
								<li>
									{importSummary.embeddings.skipped
										? '已跳过向量生成（未配置向量模型 API key）。'
										: `已为 ${importSummary.embeddings.data_rows} 行数据和 ${importSummary.embeddings.semantic_rows} 行语义数据生成向量。`}
								</li>
							) : null}
						</ul>
					</div>
				) : null}

				<div className="mt-4 flex justify-end">
					<Button
						theme={ButtonTheme.Primary}
						size={Size.REGULAR}
						type="button"
						onClick={handleRequestImport}
						disabled={!importFile || importing}
						iconPosition="left"
					>
						<Icon name={IconName.Upload} className="h-4 w-4" />
						导入
					</Button>
				</div>
			</section>

			<ConfirmModal
				open={confirmImportOpen}
				title="导入模型"
				message={
					<>
						将把 <strong>{importFile?.name}</strong> 写入目录和 语义层。
						{replace ? (
							<>
								由于已开启 <strong>替换现有数据</strong>，
								已导入数据库中、此文件里没有的语义层数据将被删除。 此操作无法撤销。
							</>
						) : null}
					</>
				}
				confirmLabel="导入"
				tone="danger"
				onConfirm={handleConfirmImport}
				onCancel={handleCancelImport}
				confirming={importing}
				error={importError}
			/>

			<Toast
				open={exportMessage !== null}
				message={exportMessage ?? ''}
				variant={ToastVariant.Success}
				onClose={() => setExportMessage(null)}
			/>
		</div>
	);
};
