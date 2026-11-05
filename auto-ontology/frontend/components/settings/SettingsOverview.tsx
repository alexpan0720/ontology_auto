// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { connectionsApi } from '@/api/connections';
import { verifiedQueriesApi } from '@/api/governance';
import { objectTypesApi } from '@/api/objects';
import { semanticCompilationApi } from '@/api/settings';
import { Icon, IconName } from '@/common/icons';
import { AdminTodos } from '@/components/homePage/AdminTodos';
import { CARD, PAGE_INTRO, PAGE_MAIN, PAGE_TITLE, SECTION_TITLE } from './pageStyles';
import { CONNECTIONS_HREF, visibleSettingsGroups } from '@/lib/settingsNavigation';

/** One step of getting a deployment to answer questions well. */
export type SetupStep = {
	key: string;
	title: string;
	description: string;
	href: string;
	/** `null` while it is being checked, or when it could not be. */
	done: boolean | null;
};

const settle = async <T,>(read: () => Promise<T>): Promise<T | null> => {
	try {
		const value = await read();
		return (value as { error?: boolean } | null)?.error ? null : value;
	} catch {
		return null;
	}
};

/**
 * The setup path in the order it has to happen: data before a semantic layer
 * can be compiled, a semantic layer before objects can be found in it, and
 * certified answers last, once there is something to certify.
 */
export const readSetupSteps = async (connectionsEnvManaged: boolean): Promise<SetupStep[]> => {
	const [connections, semantic, objects, certified] = await Promise.all([
		connectionsEnvManaged ? Promise.resolve(null) : settle(() => connectionsApi.getAll()),
		settle(() => semanticCompilationApi.getStatus()),
		settle(() => objectTypesApi.list('active')),
		settle(() => verifiedQueriesApi.list({ status: 'certified' })),
	]);
	return [
		{
			key: 'connect',
			title: '接入数据源',
			description: connectionsEnvManaged
				? '数据连接由部署配置提供。'
				: '添加要问数的数据库，系统会自动采集表和字段。',
			href: connectionsEnvManaged ? '/data' : CONNECTIONS_HREF,
			done: connectionsEnvManaged
				? true
				: connections
					? (connections.data ?? []).length > 0
					: null,
		},
		{
			key: 'compile',
			title: '生成语义层',
			description: '从表和字段的元数据推断业务含义、关联和指标口径。',
			href: '/settings/semantic-compilation',
			done: semantic ? semantic.calculated : null,
		},
		{
			key: 'objects',
			title: '确认业务对象',
			description: '把表变成客户、订单这样的业务对象，供大家按对象查看。',
			href: '/settings/object-types',
			done: objects ? objects.summary.active_types > 0 : null,
		},
		{
			key: 'certify',
			title: '认证常见问题',
			description: '认证过的问答会优先被复用，并作为推荐问题展示给所有人。',
			href: '/settings/verified-queries',
			done: certified ? certified.count > 0 : null,
		},
	];
};

const StepState = ({ done }: { done: boolean | null }) =>
	done ? (
		<span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
			<Icon name={IconName.Check} className="h-3.5 w-3.5" aria-label="已完成" />
		</span>
	) : (
		<span
			className="h-6 w-6 shrink-0 rounded-full border-2 border-zinc-300 dark:border-zinc-600"
			aria-label={done === null ? '未知' : '未完成'}
		/>
	);

/** The admin centre's landing page: setup progress, what is waiting, and the map. */
export const SettingsOverview = ({ connectionsEnvManaged }: { connectionsEnvManaged: boolean }) => {
	const [steps, setSteps] = useState<SetupStep[] | null>(null);

	useEffect(() => {
		let active = true;
		void readSetupSteps(connectionsEnvManaged).then((rows) => {
			if (active) setSteps(rows);
		});
		return () => {
			active = false;
		};
	}, [connectionsEnvManaged]);

	const finished = steps?.filter((step) => step.done).length ?? 0;
	const nextStep = steps?.find((step) => step.done === false);

	return (
		<main className={PAGE_MAIN}>
			<div className="w-full space-y-6">
				<div>
					<h1 className={PAGE_TITLE}>管理中心</h1>
					<p className={PAGE_INTRO}>
						接入数据、管理权限、提升问数质量，以及连接钉钉、飞书等工具。
					</p>
				</div>

				<section aria-labelledby="setup-title" className={CARD}>
					<div className="flex flex-wrap items-baseline justify-between gap-2">
						<h2 id="setup-title" className={SECTION_TITLE}>
							接入向导
						</h2>
						{steps && (
							<span className="text-xs text-secondary">
								已完成 {finished} / {steps.length}
							</span>
						)}
					</div>
					<ol className="mt-3 space-y-2">
						{(steps ?? []).map((step, index) => (
							<li key={step.key}>
								<Link
									href={step.href}
									className={`flex items-start gap-3 rounded-lg p-2.5 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/60 ${
										step === nextStep
											? 'bg-[#2563eb]/5 ring-1 ring-[#2563eb]/25'
											: ''
									}`}
								>
									<StepState done={step.done} />
									<span className="min-w-0">
										<span className="block text-sm font-medium text-heading dark:text-zinc-100">
											{index + 1}. {step.title}
											{step === nextStep && (
												<span className="ml-2 text-xs font-normal text-[#1d4ed8] dark:text-[#93c5fd]">
													下一步
												</span>
											)}
										</span>
										<span className="block text-xs text-secondary dark:text-zinc-400">
											{step.description}
										</span>
									</span>
								</Link>
							</li>
						))}
						{steps === null && <li className="text-xs text-secondary">正在检查…</li>}
					</ol>
				</section>

				<AdminTodos linkToSettings={false} />

				<section aria-labelledby="settings-map" className="space-y-3">
					<h2 id="settings-map" className={SECTION_TITLE}>
						全部功能
					</h2>
					<div className="grid gap-4 md:grid-cols-2">
						{visibleSettingsGroups(connectionsEnvManaged).map((group) => (
							<div key={group.key} className={CARD}>
								<h3 className="text-xs font-medium text-secondary">
									{group.title}
								</h3>
								<ul className="mt-2 grid gap-1 sm:grid-cols-2">
									{group.items.map((item) => (
										<li key={item.href}>
											<Link
												href={item.href}
												className="block rounded-md px-2 py-1.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
											>
												<span className="block text-sm text-heading dark:text-zinc-100">
													{item.label}
												</span>
												<span className="block text-[11px] text-secondary">
													{item.description}
												</span>
											</Link>
										</li>
									))}
								</ul>
							</div>
						))}
					</div>
				</section>
			</div>
		</main>
	);
};
