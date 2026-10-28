// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { glossaryImportApi } from '@/api/glossaryImport';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { FileUpload } from '@/common/FileUpload';
import { ButtonTheme, Size } from '@/enums/button';
import type {
	GlossaryCandidate,
	GlossaryImport,
	GlossaryImportDetail,
} from '@/types/glossaryImport';

const ACCEPT = '.pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md';
const SUFFIXES = ACCEPT.split(',');
const POLL_MS = 2000;

const INPUT =
	'w-full rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-body outline-none focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/20 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200';
const CARD =
	'rounded-lg border border-zinc-200/90 bg-white/90 p-4 shadow-sm ring-1 ring-zinc-950/[0.04] dark:border-zinc-700/90 dark:bg-zinc-950/50 dark:ring-white/[0.06]';

const StatusBadge = ({ batch }: { batch: GlossaryImport | GlossaryImportDetail }) => {
	if (batch.status === 'processing') {
		const pct = batch.chunks_total
			? Math.round((batch.chunks_done / batch.chunks_total) * 100)
			: 0;
		return (
			<span className="inline-flex items-center gap-2 text-xs text-[#1d4ed8] dark:text-[#60a5fa]">
				<span className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
					<span className="block h-full bg-[#2563eb]" style={{ width: `${pct}%` }} />
				</span>
				提取中 {batch.chunks_done}/{batch.chunks_total}
			</span>
		);
	}
	if (batch.status === 'failed') {
		return <span className="text-xs text-red-600 dark:text-red-400">失败</span>;
	}
	return <span className="text-xs text-secondary dark:text-zinc-400">已完成</span>;
};

/** One candidate: editable in place, saved when a field loses focus. */
const CandidateRow = ({
	candidate,
	checked,
	onCheck,
	onSaved,
}: {
	candidate: GlossaryCandidate;
	checked: boolean;
	onCheck: (checked: boolean) => void;
	onSaved: (message: string | null) => void;
}) => {
	const [term, setTerm] = useState(candidate.term);
	const [definition, setDefinition] = useState(candidate.definition);
	const [synonyms, setSynonyms] = useState(candidate.synonyms.join('、'));
	const editable = candidate.status === 'pending';

	const save = async (changes: { term?: string; definition?: string; synonyms?: string[] }) => {
		const res = await glossaryImportApi.updateCandidate(candidate.id, changes);
		onSaved(res.error ? (res.message ?? '保存失败') : null);
	};

	return (
		<li
			className={`flex gap-3 border-b border-zinc-100 py-3 last:border-0 dark:border-zinc-800 ${
				editable ? '' : 'opacity-60'
			}`}
		>
			<input
				type="checkbox"
				className="mt-1.5"
				aria-label={`选择 ${candidate.term}`}
				checked={checked}
				disabled={!editable}
				onChange={(e) => onCheck(e.target.checked)}
			/>
			<div className="flex min-w-0 flex-1 flex-col gap-1.5">
				<div className="flex flex-wrap items-center gap-2">
					<input
						aria-label="术语"
						className={`${INPUT} max-w-60 font-medium`}
						value={term}
						disabled={!editable}
						onChange={(e) => setTerm(e.target.value)}
						onBlur={() => {
							if (term.trim() && term !== candidate.term) void save({ term });
						}}
					/>
					{candidate.status === 'accepted' && (
						<span className="rounded-full bg-[#2563eb]/10 px-2 py-0.5 text-[11px] text-[#1e40af] dark:text-[#60a5fa]">
							已导入
						</span>
					)}
					{candidate.status === 'rejected' && (
						<span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] text-secondary dark:bg-zinc-800">
							已驳回
						</span>
					)}
					{/* After import the entry is this candidate's own, not a clash. */}
					{candidate.status === 'pending' && candidate.existing_definition !== null && (
						<span
							className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
							title={candidate.existing_definition}
						>
							术语表已有同名定义
						</span>
					)}
					{candidate.matched_term && (
						<span
							className="rounded-full bg-[#2563eb]/10 px-2 py-0.5 text-[11px] text-[#1e40af] dark:text-[#60a5fa]"
							title={candidate.matched_term.description ?? '暂无描述'}
						>
							匹配业务术语：{candidate.matched_term.name}
						</span>
					)}
				</div>
				<textarea
					aria-label="定义"
					className={INPUT}
					rows={2}
					value={definition}
					disabled={!editable}
					onChange={(e) => setDefinition(e.target.value)}
					onBlur={() => {
						if (definition.trim() && definition !== candidate.definition)
							void save({ definition });
					}}
				/>
				<label className="flex items-center gap-2 text-xs text-secondary dark:text-zinc-400">
					<span className="shrink-0">别名</span>
					<input
						aria-label="同义词"
						className={`${INPUT} text-xs`}
						placeholder="同义词 / 别名，用顿号或逗号分隔"
						value={synonyms}
						disabled={!editable}
						onChange={(e) => setSynonyms(e.target.value)}
						onBlur={() => {
							const list = synonyms
								.split(/[、,，;；]/)
								.map((x) => x.trim())
								.filter(Boolean);
							if (list.join('、') !== candidate.synonyms.join('、'))
								void save({ synonyms: list });
						}}
					/>
				</label>
				{candidate.evidence && (
					<p className="text-[11px] text-secondary dark:text-zinc-500">
						原文：{candidate.evidence}
					</p>
				)}
			</div>
		</li>
	);
};

export default function GlossaryImportPage() {
	const [file, setFile] = useState<File | null>(null);
	const [uploading, setUploading] = useState(false);
	const [batches, setBatches] = useState<GlossaryImport[]>([]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [detail, setDetail] = useState<GlossaryImportDetail | null>(null);
	const [checked, setChecked] = useState<Set<string>>(new Set());
	const [overwrite, setOverwrite] = useState(false);
	const [updateTerms, setUpdateTerms] = useState(true);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);

	const loadBatches = useCallback(async () => {
		const res = await glossaryImportApi.list();
		if (res.error) {
			setError(res.message ?? '加载导入记录失败');
			return;
		}
		setBatches(res.data);
	}, []);

	const loadDetail = useCallback(async (id: string) => {
		const res = await glossaryImportApi.get(id);
		if (res.error) return;
		setDetail(res);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void loadBatches();
	}, [loadBatches]);

	useEffect(() => {
		if (!selectedId) return;
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void loadDetail(selectedId);
	}, [selectedId, loadDetail]);

	// Poll while anything is still extracting, so progress and results appear on their own.
	const processing = batches.some((b) => b.status === 'processing');
	useEffect(() => {
		if (!processing) return;
		const timer = window.setInterval(() => {
			void loadBatches();
			if (selectedId) void loadDetail(selectedId);
		}, POLL_MS);
		return () => window.clearInterval(timer);
	}, [processing, selectedId, loadBatches, loadDetail]);

	const pending = useMemo(
		() => (detail?.candidates ?? []).filter((c) => c.status === 'pending'),
		[detail],
	);
	const chosen = pending.filter((c) => checked.has(c.id));

	const upload = async () => {
		if (!file || uploading) return;
		setUploading(true);
		setError(null);
		setNotice(null);
		const res = await glossaryImportApi.upload(file);
		setUploading(false);
		if (res.error) {
			setError(res.message ?? '上传失败');
			return;
		}
		setFile(null);
		setChecked(new Set());
		setSelectedId(res.id);
		await loadBatches();
	};

	const apply = async () => {
		if (!detail || chosen.length === 0 || busy) return;
		setBusy(true);
		setNotice(null);
		const res = await glossaryImportApi.apply(detail.id, {
			candidate_ids: chosen.map((c) => c.id),
			overwrite_existing: overwrite,
			update_terms: updateTerms,
		});
		setBusy(false);
		if (res.error) {
			setError(res.message ?? '导入失败');
			return;
		}
		const parts = [`新增 ${res.added} 条`];
		if (res.replaced) parts.push(`覆盖 ${res.replaced} 条`);
		if (res.skipped) parts.push(`跳过同名 ${res.skipped} 条`);
		if (res.terms_updated) parts.push(`更新业务术语描述 ${res.terms_updated} 个`);
		setNotice(`已导入术语表：${parts.join('，')}。问数时会自动参考这些定义。`);
		setChecked(new Set());
		await Promise.all([loadDetail(detail.id), loadBatches()]);
	};

	const reject = async () => {
		if (!detail || chosen.length === 0 || busy) return;
		setBusy(true);
		const res = await glossaryImportApi.reject(
			detail.id,
			chosen.map((c) => c.id),
		);
		setBusy(false);
		if (res.error) setError(res.message ?? '操作失败');
		setChecked(new Set());
		await Promise.all([loadDetail(detail.id), loadBatches()]);
	};

	const remove = async (batch: GlossaryImport) => {
		if (
			!window.confirm(
				`确定删除“${batch.file_name}”的导入记录吗？已导入术语表的内容不受影响。`,
			)
		)
			return;
		await glossaryImportApi.remove(batch.id);
		if (selectedId === batch.id) {
			setSelectedId(null);
			setDetail(null);
		}
		await loadBatches();
	};

	return (
		<main className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-[linear-gradient(180deg,rgba(255,255,255,1)_0%,rgba(250,250,250,0.6)_100%)] px-7 py-6 sm:px-10 sm:py-7 dark:bg-[linear-gradient(180deg,rgba(9,9,11,1)_0%,rgba(24,24,27,0.5)_100%)]">
			<div className="w-full space-y-5">
				<div>
					<h1 className="text-base font-semibold text-heading dark:text-zinc-100">
						文档提取术语
					</h1>
					<p className="mt-1 max-w-3xl text-xs text-secondary dark:text-zinc-400">
						上传数据字典、指标口径说明、管理制度等文档，AI
						会自动提取其中的业务术语和定义。审核确认后写入“语义输入 →
						术语表”，问数时自动参考；与已有业务术语同名时，还可以一并更新该术语的描述。
					</p>
				</div>

				<section className={CARD}>
					<FileUpload
						value={file}
						onChange={(f) => {
							setError(null);
							setFile(f);
						}}
						accept={ACCEPT}
						disabled={uploading}
						description="支持 PDF、Word（.docx）、Excel（.xlsx）、CSV、TXT、Markdown，单个文件不超过 20 MB；扫描版 PDF 无法提取"
						validate={(f) =>
							SUFFIXES.some((s) => f.name.toLowerCase().endsWith(s))
								? null
								: '不支持的文件类型'
						}
						onError={setError}
						aria-label="上传文档"
					/>
					<div className="mt-3 flex justify-end">
						<Button
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							disabled={!file || uploading}
							onClick={() => {
								void upload();
							}}
						>
							{uploading ? '正在解析…' : '开始提取'}
						</Button>
					</div>
				</section>

				{error && (
					<p role="alert" className="text-xs text-red-600 dark:text-red-400">
						{error}
					</p>
				)}
				{notice && (
					<p role="status" className="text-xs text-[#1d4ed8] dark:text-[#60a5fa]">
						{notice}
					</p>
				)}

				<section className={CARD}>
					<h2 className="mb-2 text-sm font-semibold text-heading dark:text-zinc-100">
						导入记录
					</h2>
					{batches.length === 0 ? (
						<p className="text-xs text-secondary">还没有上传过文档。</p>
					) : (
						<ul className="flex flex-col">
							{batches.map((b) => (
								<li
									key={b.id}
									className={`flex flex-wrap items-center gap-3 border-b border-zinc-100 px-2 py-2 text-sm last:border-0 dark:border-zinc-800 ${
										selectedId === b.id ? 'rounded-md bg-[#2563eb]/5' : ''
									}`}
								>
									<button
										type="button"
										className="min-w-0 flex-1 truncate text-left text-heading hover:text-[#2563eb] dark:text-zinc-100"
										onClick={() => {
											setChecked(new Set());
											setNotice(null);
											setSelectedId(b.id);
										}}
									>
										{b.file_name}
									</button>
									<StatusBadge batch={b} />
									<span className="text-xs text-secondary dark:text-zinc-400">
										待审核 {b.counts.pending} · 已导入 {b.counts.accepted} ·
										已驳回 {b.counts.rejected}
									</span>
									<span className="text-xs text-secondary">
										{b.created ? formatDate(b.created, 'MM-DD HH:mm') : ''}
									</span>
									<button
										type="button"
										className="text-xs text-red-600 hover:underline dark:text-red-400"
										onClick={() => {
											void remove(b);
										}}
									>
										删除
									</button>
								</li>
							))}
						</ul>
					)}
				</section>

				{detail && (
					<section className={CARD}>
						<div className="flex flex-wrap items-center justify-between gap-2">
							<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
								{detail.file_name} 的候选术语
							</h2>
							<StatusBadge batch={detail} />
						</div>
						{detail.status === 'failed' && (
							<p className="mt-2 text-xs text-red-600 dark:text-red-400">
								{detail.error_message}
							</p>
						)}
						{detail.truncated && (
							<p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
								文档较长，只提取了前 {detail.chunks_total}{' '}
								段内容；如需完整提取，请拆分文档后分别上传。
							</p>
						)}
						{detail.status === 'processing' && (
							<p className="mt-2 text-xs text-secondary">
								正在逐段提取，完成后候选术语会自动出现在这里。
							</p>
						)}
						{detail.status === 'done' && detail.candidates.length === 0 && (
							<p className="mt-2 text-xs text-secondary">
								没有在文档中找到术语定义。
							</p>
						)}

						{detail.candidates.length > 0 && (
							<>
								<div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md bg-zinc-50 px-3 py-2 text-xs dark:bg-zinc-900">
									<label className="flex items-center gap-1.5 text-body dark:text-zinc-300">
										<input
											type="checkbox"
											checked={
												pending.length > 0 &&
												chosen.length === pending.length
											}
											onChange={(e) =>
												setChecked(
													e.target.checked
														? new Set(pending.map((c) => c.id))
														: new Set(),
												)
											}
										/>
										全选待审核（{pending.length}）
									</label>
									<label className="flex items-center gap-1.5 text-body dark:text-zinc-300">
										<input
											type="checkbox"
											checked={updateTerms}
											onChange={(e) => setUpdateTerms(e.target.checked)}
										/>
										同时更新匹配业务术语的描述
									</label>
									<label className="flex items-center gap-1.5 text-body dark:text-zinc-300">
										<input
											type="checkbox"
											checked={overwrite}
											onChange={(e) => setOverwrite(e.target.checked)}
										/>
										覆盖术语表中的同名定义
									</label>
									<span className="ml-auto flex gap-2">
										<Button
											theme={ButtonTheme.Secondary}
											size={Size.SMALL}
											disabled={chosen.length === 0 || busy}
											onClick={() => {
												void reject();
											}}
										>
											驳回所选
										</Button>
										<Button
											theme={ButtonTheme.Primary}
											size={Size.SMALL}
											disabled={chosen.length === 0 || busy}
											onClick={() => {
												void apply();
											}}
										>
											导入所选（{chosen.length}）
										</Button>
									</span>
								</div>
								<ul className="mt-1">
									{detail.candidates.map((c) => (
										<CandidateRow
											key={c.id}
											candidate={c}
											checked={checked.has(c.id)}
											onCheck={(on) => {
												const next = new Set(checked);
												if (on) next.add(c.id);
												else next.delete(c.id);
												setChecked(next);
											}}
											onSaved={setError}
										/>
									))}
								</ul>
							</>
						)}
					</section>
				)}
			</div>
		</main>
	);
}
