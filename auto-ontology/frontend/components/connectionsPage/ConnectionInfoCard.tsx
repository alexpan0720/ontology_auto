// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { Button } from '@/common/Button';
import { Size, ButtonTheme } from '@/enums/button';
import { Icon, IconName } from '@/common/icons';
import { PopoverMenu } from '@/common/PopoverMenu';
import { Text } from '@/common/Text';
import { TextVariant } from '@/enums/text';
import { ConnectionType } from '@/enums/connection';
import type { Connection } from '@/types/connection';

export type ConnectionInfoCardProps = {
	connection: Connection;
	onEdit?: (connection: Connection) => void;
	onDelete?: (databaseName: string) => void;
	onSsoFederationChange?: (databaseName: string, enabled: boolean) => void;
	/** Disables the toggle while its request is in flight. */
	ssoFederationPending?: boolean;
	disabled?: boolean;
};

export const ConnectionInfoCard = ({
	connection,
	onEdit,
	onDelete,
	onSsoFederationChange,
	ssoFederationPending = false,
	disabled = false,
}: ConnectionInfoCardProps) => {
	const menuItems = [
		...(onEdit == null
			? []
			: [
					{
						label: '编辑',
						icon: <Icon name={IconName.Pencil} className="h-3.5 w-3.5" />,
						onClick: () => onEdit(connection),
					},
				]),
		...(onDelete == null
			? []
			: [
					{
						label: '移除',
						icon: <Icon name={IconName.Trash} className="h-3.5 w-3.5" />,
						onClick: () => onDelete(connection.database_name),
						danger: true,
					},
				]),
	];
	const menuDisabled = disabled || menuItems.length === 0;
	// Only Databricks supports authenticating as the signed-in user.
	const databricks =
		connection.connection.type === ConnectionType.DATABRICKS ? connection.connection : null;
	const showSsoFederation = databricks != null && onSsoFederationChange != null;
	const ssoFederationOn = databricks?.sso_federation === true;

	return (
		<article className="flex h-fit flex-col rounded-lg border border-zinc-200/90 bg-white shadow-sm dark:border-zinc-700/90 dark:bg-zinc-950">
			<header className="flex w-full items-center justify-between gap-2 px-4 py-5">
				<div className="flex min-w-0 items-center gap-1">
					<Icon
						name={IconName.Database}
						className="h-5 w-5 shrink-0 text-body dark:text-zinc-300"
					/>
					<Text
						as="h3"
						text={connection.database_name}
						variant={TextVariant.Subheading}
					/>
				</div>
				<div className="relative shrink-0">
					{menuDisabled ? (
						<Icon
							name={IconName.DotsVertical}
							className="h-4 w-4 text-disabled dark:text-zinc-600"
						/>
					) : (
						<PopoverMenu
							className="relative"
							items={menuItems}
							trigger={({ toggle }) => (
								<Button
									theme={ButtonTheme.IconNeutral}
									size={Size.SMALL}
									iconOnly
									type="button"
									onClick={toggle}
									aria-label={`${connection.database_name} 的操作`}
								>
									<Icon name={IconName.DotsVertical} className="h-4 w-4" />
								</Button>
							)}
						/>
					)}
				</div>
			</header>
			{showSsoFederation && (
				<div className="border-t border-zinc-200/90 px-4 py-3 dark:border-zinc-700/90">
					<label className="flex cursor-pointer items-start gap-2">
						<input
							type="checkbox"
							checked={ssoFederationOn}
							disabled={disabled || ssoFederationPending}
							onChange={({ target }) =>
								onSsoFederationChange(connection.database_name, target.checked)
							}
							data-testid={`sso-federation-${connection.database_name}`}
							className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-zinc-300 accent-[#2563eb] disabled:cursor-default dark:border-zinc-600"
						/>
						<span className="min-w-0">
							<span className="block text-xs font-medium text-heading dark:text-zinc-200">
								以当前登录用户身份认证
							</span>
							<span className="block text-xs text-secondary dark:text-zinc-400">
								{ssoFederationOn
									? '对话以每个用户自己的 Databricks 权限执行 SQL。'
									: '对话使用此连接保存的访问令牌执行 SQL。'}
							</span>
						</span>
					</label>
				</div>
			)}
		</article>
	);
};
