// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState } from 'react';
import { pushChannelsApi } from '@/api/subscriptions';
import { Button } from '@/common/Button';
import { ConfirmModal, Modal } from '@/common/modal';
import {
	BADGE,
	BADGE_TONE,
	CARD,
	INPUT,
	LABEL,
	NOTICE_ERROR,
	NOTICE_OK,
	SECTION_TITLE,
} from '@/components/settings/pageStyles';
import { ButtonTheme, Size } from '@/enums/button';
import type { PushChannel, PushPlatform } from '@/types/subscriptions';

export const PLATFORM_NAME: Record<PushPlatform, string> = { dingtalk: '钉钉', feishu: '飞书' };

const GUIDE: Record<PushPlatform, string[]> = {
	dingtalk: [
		'在钉钉群里打开“群设置 → 机器人 → 添加机器人 → 自定义”。',
		'安全设置勾选“加签”，复制密钥（以 SEC 开头）填到下方；不建议用“自定义关键词”。',
		'完成后复制 Webhook 地址（https://oapi.dingtalk.com/robot/send?access_token=…）。',
	],
	feishu: [
		'在飞书群里打开“设置 → 群机器人 → 添加机器人 → 自定义机器人”。',
		'安全设置开启“签名校验”，复制密钥填到下方。',
		'复制 Webhook 地址（https://open.feishu.cn/open-apis/bot/v2/hook/…）。',
	],
};

const ChannelDialog = ({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) => {
	const [platform, setPlatform] = useState<PushPlatform>('dingtalk');
	const [name, setName] = useState('');
	const [url, setUrl] = useState('');
	const [secret, setSecret] = useState('');
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

	const test = async () => {
		setBusy(true);
		setMessage(null);
		const res = await pushChannelsApi.test({ platform, webhook_url: url, secret });
		setBusy(false);
		setMessage(
			res.error
				? { ok: false, text: res.message ?? '测试失败' }
				: { ok: res.ok, text: res.ok ? '测试消息已发到群里，请到群中确认。' : res.message },
		);
	};

	const save = async () => {
		setBusy(true);
		setMessage(null);
		const res = await pushChannelsApi.create({ name, platform, webhook_url: url, secret });
		setBusy(false);
		if (res.error) {
			setMessage({ ok: false, text: res.message ?? '保存失败' });
			return;
		}
		onSaved();
	};

	return (
		<form
			className="flex flex-col gap-3 p-5"
			onSubmit={(e) => {
				e.preventDefault();
				void save();
			}}
		>
			<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">添加推送渠道</h2>
			<div className="flex gap-2" role="radiogroup" aria-label="平台">
				{(['dingtalk', 'feishu'] as const).map((p) => (
					<button
						key={p}
						type="button"
						role="radio"
						aria-checked={platform === p}
						onClick={() => setPlatform(p)}
						className={`rounded-lg border px-4 py-1.5 text-sm ${
							platform === p
								? 'border-[#2563eb] bg-[#2563eb]/10 text-[#1e40af] dark:text-[#60a5fa]'
								: 'border-zinc-300 text-body dark:border-zinc-600 dark:text-zinc-300'
						}`}
					>
						{PLATFORM_NAME[p]}群
					</button>
				))}
			</div>
			<ol className="list-decimal space-y-1 rounded-md bg-zinc-50 py-2 pl-7 pr-3 text-xs text-body dark:bg-zinc-900 dark:text-zinc-300">
				{GUIDE[platform].map((step) => (
					<li key={step}>{step}</li>
				))}
			</ol>
			<label className={LABEL}>
				名称
				<input
					className={INPUT}
					value={name}
					placeholder="例如：经营管理群"
					onChange={(e) => setName(e.target.value)}
				/>
			</label>
			<label className={LABEL}>
				Webhook 地址
				<input
					className={`${INPUT} font-mono text-xs`}
					value={url}
					autoComplete="off"
					onChange={(e) => setUrl(e.target.value)}
				/>
			</label>
			<label className={LABEL}>
				加签密钥（推荐）
				<input
					className={INPUT}
					type="password"
					value={secret}
					autoComplete="new-password"
					onChange={(e) => setSecret(e.target.value)}
				/>
			</label>
			{message && <p className={message.ok ? NOTICE_OK : NOTICE_ERROR}>{message.text}</p>}
			<div className="flex justify-end gap-2">
				<Button theme={ButtonTheme.Secondary} size={Size.SMALL} onClick={onClose}>
					取消
				</Button>
				<Button
					theme={ButtonTheme.Secondary}
					size={Size.SMALL}
					disabled={busy || !url.trim()}
					onClick={() => {
						void test();
					}}
				>
					发送测试消息
				</Button>
				<Button
					theme={ButtonTheme.Primary}
					size={Size.SMALL}
					type="submit"
					disabled={busy || !name.trim() || !url.trim()}
				>
					保存
				</Button>
			</div>
		</form>
	);
};

export const ChannelsSection = ({
	channels,
	onChanged,
}: {
	channels: PushChannel[];
	onChanged: () => Promise<void>;
}) => {
	const [adding, setAdding] = useState(false);
	const [deleting, setDeleting] = useState<PushChannel | null>(null);
	const [status, setStatus] = useState<Record<string, { ok: boolean; text: string }>>({});

	const test = async (channel: PushChannel) => {
		setStatus((s) => ({ ...s, [channel.id]: { ok: true, text: '发送中…' } }));
		const res = await pushChannelsApi.test({ channel_id: channel.id });
		setStatus((s) => ({
			...s,
			[channel.id]: res.error
				? { ok: false, text: res.message ?? '测试失败' }
				: { ok: res.ok, text: res.ok ? '已发送测试消息' : res.message },
		}));
	};

	return (
		<section className={CARD}>
			<div className="flex flex-wrap items-center justify-between gap-2">
				<div>
					<h2 className={SECTION_TITLE}>推送渠道</h2>
					<p className="mt-0.5 text-xs text-secondary dark:text-zinc-400">
						钉钉群或飞书群的自定义机器人。添加一次，所有订阅都可以选择推送到这里。
					</p>
				</div>
				<Button
					theme={ButtonTheme.Secondary}
					size={Size.SMALL}
					onClick={() => setAdding(true)}
				>
					添加渠道
				</Button>
			</div>
			{channels.length === 0 ? (
				<p className="mt-3 text-xs text-secondary dark:text-zinc-400">
					还没有推送渠道。先添加一个群机器人，再创建订阅。
				</p>
			) : (
				<ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
					{channels.map((c) => (
						<li
							key={c.id}
							className="flex flex-wrap items-center justify-between gap-3 py-2.5"
						>
							<div className="min-w-0">
								<p className="text-sm text-heading dark:text-zinc-100">
									<span className={`${BADGE} ${BADGE_TONE.blue} mr-2`}>
										{PLATFORM_NAME[c.platform]}
									</span>
									{c.name}
									{!c.has_secret && (
										<span
											className={`${BADGE} ${BADGE_TONE.amber} ml-2`}
											title="建议在机器人安全设置中开启加签"
										>
											未加签
										</span>
									)}
								</p>
								<p className="mt-0.5 truncate font-mono text-[11px] text-secondary">
									{c.webhook_hint}
								</p>
								{status[c.id] && (
									<p className={status[c.id].ok ? NOTICE_OK : NOTICE_ERROR}>
										{status[c.id].text}
									</p>
								)}
							</div>
							<div className="flex gap-2">
								<Button
									theme={ButtonTheme.Secondary}
									size={Size.SMALL}
									onClick={() => {
										void test(c);
									}}
								>
									测试
								</Button>
								<Button
									theme={ButtonTheme.Secondary}
									size={Size.SMALL}
									onClick={() => setDeleting(c)}
								>
									删除
								</Button>
							</div>
						</li>
					))}
				</ul>
			)}
			<Modal open={adding} onClose={() => setAdding(false)} className="w-full max-w-lg">
				{adding && (
					<ChannelDialog
						onClose={() => setAdding(false)}
						onSaved={() => {
							setAdding(false);
							void onChanged();
						}}
					/>
				)}
			</Modal>
			<ConfirmModal
				open={deleting !== null}
				title="删除推送渠道"
				message={`删除“${deleting?.name ?? ''}”后，订阅将不再推送到这个群。`}
				onCancel={() => setDeleting(null)}
				onConfirm={async () => {
					if (deleting) await pushChannelsApi.remove(deleting.id);
					setDeleting(null);
					await onChanged();
				}}
			/>
		</section>
	);
};
