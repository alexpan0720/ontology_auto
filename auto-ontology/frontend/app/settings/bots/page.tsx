// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useCallback, useEffect, useState } from 'react';
import { botsApi } from '@/api/bots';
import { Button } from '@/common/Button';
import { formatDate } from '@/common/date';
import { ButtonTheme, Size } from '@/enums/button';
import type { BotPlatform, BotSettings } from '@/types/bots';
import { CARD, INPUT, PAGE_MAIN } from '@/components/settings/pageStyles';

const POLL_MS = 5000;

type PlatformInfo = {
	name: string;
	idLabel: string;
	secretLabel: string;
	steps: string[];
};

const PLATFORMS: Record<BotPlatform, PlatformInfo> = {
	dingtalk: {
		name: '钉钉',
		idLabel: 'Client ID（AppKey）',
		secretLabel: 'Client Secret（AppSecret）',
		steps: [
			'登录钉钉开放平台（open-dingtalk.com），在“应用开发 → 企业内部应用”中创建应用。',
			'在应用的“机器人”能力中开启机器人，消息接收模式选择“Stream 模式”（无需公网地址）。',
			'在“权限管理”中申请“通讯录个人信息读权限”，用于按邮箱匹配本系统账号；未开通时所有提问者按最严格权限处理。',
			'在“凭证与基础信息”中复制 Client ID 和 Client Secret 填到下方，测试通过后启用并保存。',
			'发布应用版本后，在钉钉中搜索机器人单聊，或把机器人拉进群并 @它 提问。',
		],
	},
	feishu: {
		name: '飞书',
		idLabel: 'App ID',
		secretLabel: 'App Secret',
		steps: [
			'登录飞书开放平台（open.feishu.cn），创建“企业自建应用”，并在“添加应用能力”中添加“机器人”。',
			'在“权限管理”中开通：im:message（读取单聊和群聊中 @机器人 的消息）、im:message:send_as_bot（以应用身份发消息）、contact:user.email:readonly（读取用户邮箱，用于匹配本系统账号）。',
			'在“事件与回调 → 事件配置”中，订阅方式选择“使用长连接接收事件”（无需公网地址），并添加事件“接收消息 im.message.receive_v1”。',
			'在“凭证与基础信息”中复制 App ID 和 App Secret 填到下方，测试通过后启用并保存。',
			'创建并发布应用版本后，在飞书中搜索机器人单聊，或把机器人拉进群并 @它 提问。',
		],
	},
};

const StatusLine = ({ settings }: { settings: BotSettings }) => {
	const when = settings.status_updated
		? `（${formatDate(settings.status_updated, 'MM-DD HH:mm:ss')}）`
		: '';
	if (!settings.enabled) {
		return <span className="text-xs text-secondary dark:text-zinc-400">未启用</span>;
	}
	if (settings.status === 'connected') {
		return (
			<span className="text-xs text-emerald-600 dark:text-emerald-400">
				● 已连接 {settings.status_detail ?? ''}
				{when}
			</span>
		);
	}
	if (settings.status === 'error') {
		return (
			<span className="text-xs text-red-600 dark:text-red-400">
				● 连接失败：{settings.status_detail ?? '未知原因'}
				{when}
			</span>
		);
	}
	return (
		<span className="text-xs text-amber-600 dark:text-amber-400">
			● 正在连接，通常在 15 秒内完成…
		</span>
	);
};

const BotCard = ({
	settings,
	onSaved,
}: {
	settings: BotSettings;
	onSaved: () => Promise<void>;
}) => {
	const info = PLATFORMS[settings.platform];
	const [enabled, setEnabled] = useState(settings.enabled);
	const [appId, setAppId] = useState(settings.app_id);
	const [secret, setSecret] = useState('');
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
	const [showSteps, setShowSteps] = useState(!settings.app_id);

	const dirty = enabled !== settings.enabled || appId !== settings.app_id || secret !== '';

	const test = async () => {
		setBusy(true);
		setMessage(null);
		const res = await botsApi.test(settings.platform, {
			app_id: appId,
			app_secret: secret || undefined,
		});
		setBusy(false);
		setMessage(
			res.error
				? { ok: false, text: res.message ?? '测试失败' }
				: { ok: res.ok, text: res.message },
		);
	};

	const save = async () => {
		setBusy(true);
		setMessage(null);
		const res = await botsApi.save(settings.platform, {
			enabled,
			app_id: appId,
			app_secret: secret || undefined,
		});
		setBusy(false);
		if (res.error) {
			setMessage({ ok: false, text: res.message ?? '保存失败' });
			return;
		}
		setSecret('');
		setMessage({
			ok: true,
			text: enabled
				? '已保存，机器人服务会在 15 秒内用新设置重新连接。'
				: '已保存，机器人已停用。',
		});
		await onSaved();
	};

	return (
		<section className={CARD}>
			<div className="flex flex-wrap items-center justify-between gap-3">
				<div>
					<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">
						{info.name}机器人
					</h2>
					<StatusLine settings={settings} />
				</div>
				<label className="flex items-center gap-2 text-sm text-body dark:text-zinc-300">
					<button
						type="button"
						role="switch"
						aria-checked={enabled}
						aria-label={`启用${info.name}机器人`}
						onClick={() => setEnabled(!enabled)}
						className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
							enabled ? 'bg-[#2563eb]' : 'bg-zinc-300 dark:bg-zinc-600'
						}`}
					>
						<span
							className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
								enabled ? 'translate-x-5' : 'translate-x-0.5'
							}`}
						/>
					</button>
					启用
				</label>
			</div>

			<div className="mt-4 grid gap-3 sm:grid-cols-2">
				<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
					{info.idLabel}
					<input
						className={INPUT}
						value={appId}
						onChange={(e) => setAppId(e.target.value)}
						autoComplete="off"
					/>
				</label>
				<label className="flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400">
					{info.secretLabel}
					<input
						className={INPUT}
						type="password"
						value={secret}
						onChange={(e) => setSecret(e.target.value)}
						placeholder={settings.has_secret ? '已保存，留空则不修改' : ''}
						autoComplete="new-password"
					/>
				</label>
			</div>

			{message && (
				<p
					role="status"
					className={`mt-3 text-xs ${message.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}
				>
					{message.text}
				</p>
			)}

			<div className="mt-4 flex flex-wrap items-center justify-between gap-2">
				<button
					type="button"
					className="text-xs text-[#2563eb] hover:underline dark:text-[#60a5fa]"
					aria-expanded={showSteps}
					onClick={() => setShowSteps(!showSteps)}
				>
					{showSteps ? '收起配置步骤' : `查看${info.name}配置步骤`}
				</button>
				<div className="flex gap-2">
					<Button
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						disabled={busy || !appId || (!secret && !settings.has_secret)}
						onClick={() => {
							void test();
						}}
					>
						测试连接
					</Button>
					<Button
						theme={ButtonTheme.Primary}
						size={Size.SMALL}
						disabled={busy || !dirty}
						onClick={() => {
							void save();
						}}
					>
						{busy ? '处理中…' : '保存'}
					</Button>
				</div>
			</div>

			{showSteps && (
				<ol className="mt-3 list-decimal space-y-1.5 rounded-md bg-zinc-50 py-3 pl-8 pr-4 text-xs text-body dark:bg-zinc-900 dark:text-zinc-300">
					{info.steps.map((step) => (
						<li key={step}>{step}</li>
					))}
				</ol>
			)}
		</section>
	);
};

export default function BotsPage() {
	const [bots, setBots] = useState<BotSettings[] | null>(null);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		const res = await botsApi.list();
		if (res.error) {
			setError(res.message ?? '加载机器人设置失败');
			return;
		}
		setError(null);
		setBots(res.data);
	}, []);

	useEffect(() => {
		// eslint-disable-next-line react-hooks/set-state-in-effect -- awaited inside load
		void load();
		// Connection status is written by the bot service; keep it current.
		const timer = window.setInterval(() => {
			void load();
		}, POLL_MS);
		return () => window.clearInterval(timer);
	}, [load]);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-5">
				<div>
					<h1 className="text-base font-semibold text-heading dark:text-zinc-100">
						机器人
					</h1>
					<p className="mt-1 max-w-3xl text-xs text-secondary dark:text-zinc-400">
						在钉钉、飞书里直接用自然语言问数。机器人通过 Stream 模式 /
						长连接主动连接平台，本地部署也无需公网地址。提问人按企业邮箱匹配本系统账号，套用该账号的数据权限和脱敏规则，并记入访问审计；匹配不到账号的人按无任何用户组的普通用户处理。
					</p>
				</div>
				{error && (
					<p role="alert" className="text-xs text-red-600 dark:text-red-400">
						{error}
					</p>
				)}
				{bots === null ? (
					<p className="text-xs text-secondary">加载中…</p>
				) : (
					bots.map((b) => <BotCard key={b.platform} settings={b} onSaved={load} />)
				)}
			</div>
		</main>
	);
}
