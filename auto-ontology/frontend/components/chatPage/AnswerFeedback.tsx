// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState } from 'react';
import { conversationsApi } from '@/api/conversations';
import { verifiedQueriesApi } from '@/api/governance';
import { Button } from '@/common/Button';
import { Modal } from '@/common/modal';
import { ButtonTheme, Size } from '@/enums/button';

type AnswerFeedbackProps = {
	conversationId: string;
	messageId: string;
	question: string;
	sql: string;
	databaseName?: string;
	initial?: 'up' | 'down';
};

const ThumbIcon = ({ down = false }: { down?: boolean }) => (
	<svg
		viewBox="0 0 24 24"
		aria-hidden
		className={`h-3.5 w-3.5 ${down ? 'rotate-180' : ''}`}
		fill="none"
		stroke="currentColor"
		strokeWidth={1.8}
		strokeLinecap="round"
		strokeLinejoin="round"
	>
		<path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3Zm0 0 4-7a2 2 0 0 1 3 1.7V9h5.2a2 2 0 0 1 2 2.3l-1.3 8A2 2 0 0 1 17 21H7" />
	</svg>
);

/**
 * Rate an SQL answer. A thumbs-up offers the question and its SQL to the
 * verified-query library; a thumbs-down asks what was wrong and, when the asker
 * supplies corrected SQL, offers that instead. Either lands as `pending` until
 * a reviewer certifies it under Settings → 认证问答库.
 */
export const AnswerFeedback = ({
	conversationId,
	messageId,
	question,
	sql,
	databaseName,
	initial,
}: AnswerFeedbackProps) => {
	const [rating, setRating] = useState<'up' | 'down' | undefined>(initial);
	const [dialogOpen, setDialogOpen] = useState(false);
	const [note, setNote] = useState('');
	const [correctedSql, setCorrectedSql] = useState('');
	const [busy, setBusy] = useState(false);
	const [status, setStatus] = useState<string | null>(null);

	const save = async (next: 'up' | 'down' | null, noteText?: string): Promise<boolean> => {
		try {
			await conversationsApi.setFeedback(conversationId, messageId, next, noteText);
			setRating(next ?? undefined);
			return true;
		} catch {
			setStatus('反馈保存失败，请重试');
			return false;
		}
	};

	const submitToLibrary = async (sqlText: string, noteText?: string) => {
		const res = await verifiedQueriesApi.submit({
			question,
			sql: sqlText,
			database_name: databaseName ?? null,
			note: noteText ?? null,
		});
		setStatus(
			res.error ? '已记录反馈，但提交到问答库失败' : '已提交到认证问答库，等待管理员审核',
		);
	};

	const handleUp = async () => {
		if (busy) return;
		setBusy(true);
		setStatus(null);
		if (rating === 'up') {
			await save(null);
		} else if (await save('up')) {
			await submitToLibrary(sql);
		}
		setBusy(false);
	};

	const handleDownSubmit = async () => {
		if (busy) return;
		setBusy(true);
		setStatus(null);
		const trimmedNote = note.trim();
		if (await save('down', trimmedNote)) {
			// Only a changed query is a correction; the field starts as the original.
			const fixed = correctedSql.trim();
			if (fixed && fixed !== sql.trim())
				await submitToLibrary(fixed, trimmedNote || '用户修正的 SQL');
			else setStatus('已记录反馈，谢谢');
			setDialogOpen(false);
		}
		setBusy(false);
	};

	const pillClass = (active: boolean) =>
		`inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs transition-colors disabled:opacity-50 ${
			active
				? 'bg-[#2563eb]/10 text-[#2563eb] dark:text-[#60a5fa]'
				: 'text-secondary hover:bg-zinc-200/70 hover:text-heading dark:text-zinc-400 dark:hover:bg-zinc-700'
		}`;

	return (
		<div className="mt-2 flex flex-wrap items-center gap-1">
			<button
				type="button"
				aria-label="回答正确"
				aria-pressed={rating === 'up'}
				title="回答正确，提交到认证问答库"
				disabled={busy}
				onClick={() => {
					void handleUp();
				}}
				className={pillClass(rating === 'up')}
			>
				<ThumbIcon />
				有用
			</button>
			<button
				type="button"
				aria-label="回答有误"
				aria-pressed={rating === 'down'}
				title="回答有误，可以提交修正后的 SQL"
				disabled={busy}
				onClick={() => {
					if (rating === 'down') {
						void save(null);
						return;
					}
					setNote('');
					setCorrectedSql(sql);
					setDialogOpen(true);
				}}
				className={pillClass(rating === 'down')}
			>
				<ThumbIcon down />
				有误
			</button>
			{status && (
				<span role="status" className="ml-1 text-[11px] text-secondary dark:text-zinc-400">
					{status}
				</span>
			)}

			<Modal
				open={dialogOpen}
				onClose={() => setDialogOpen(false)}
				className="w-full max-w-xl"
			>
				<form
					className="flex flex-col gap-3 p-5"
					onSubmit={(e) => {
						e.preventDefault();
						void handleDownSubmit();
					}}
				>
					<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
						这个回答哪里不对？
					</h2>
					<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
						问题说明（可选）
						<textarea
							value={note}
							onChange={(e) => setNote(e.target.value)}
							rows={2}
							placeholder="例如：销售额应该只算已完成的订单"
							className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-body outline-none focus:border-[#2563eb] dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200"
						/>
					</label>
					<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
						修正后的
						SQL（可选，填写后会提交到认证问答库，管理员审核通过后用于改进同类问题）
						<textarea
							value={correctedSql}
							onChange={(e) => setCorrectedSql(e.target.value)}
							rows={7}
							spellCheck={false}
							className="rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-xs text-body outline-none focus:border-[#2563eb] dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200"
						/>
					</label>
					<div className="flex justify-end gap-2">
						<Button
							type="button"
							theme={ButtonTheme.Secondary}
							size={Size.SMALL}
							onClick={() => setDialogOpen(false)}
						>
							取消
						</Button>
						<Button
							type="submit"
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							disabled={busy}
						>
							提交反馈
						</Button>
					</div>
				</form>
			</Modal>
		</div>
	);
};
