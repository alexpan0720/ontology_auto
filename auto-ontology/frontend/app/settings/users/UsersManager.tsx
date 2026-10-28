// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSession } from '@/auth/auth-client';
import { Role } from '@/enums/auth';
import { invitationsApi } from '@/api/invitations';
import { usersApi } from '@/api/users';
import { Button, CopyButton } from '@/common/Button';
import { formatDate } from '@/common/date';
import { Icon, IconName } from '@/common/icons';
import { Size, ButtonTheme } from '@/enums/button';
import { InvitationKind, InvitationStatus } from '@/enums/invitation';
import { ToastVariant } from '@/enums/toast';
import { Table } from '@/common/Table';
import { SkeletonTable } from '@/common/Skeleton';
import { Toast } from '@/common/Toast';
import { PopoverMenu } from '@/common/PopoverMenu';
import { ConfirmModal } from '@/common/modal';
import type { TableColumn } from '@/types/table';
import type { UpdateUserInput, User } from '@/types/auth';
import type { Invitation } from '@/types/invitation';
import { invalidateOwners } from '@/lib/queries/owners';
import { GroupsSection } from './GroupsSection';
import { EditUserModal } from './EditUserModal';
import { InviteUserModal, type InviteUserInput } from './InviteUserModal';

const invitationStatusLabel: Record<InvitationStatus, string> = {
	[InvitationStatus.Active]: '有效',
	[InvitationStatus.Expired]: '已过期',
};

const invitationKindLabel: Record<InvitationKind, string> = {
	[InvitationKind.Invite]: '邀请',
	[InvitationKind.Reset]: '重置密码',
};

const actionErrorMessage = (error: unknown, fallback: string): string => {
	if (typeof error === 'object' && error && 'message' in error) {
		const message = (error as { message?: string }).message;
		if (message) return message;
	}
	return fallback;
};

export const UsersManager = () => {
	const queryClient = useQueryClient();
	const { data: session } = useSession();
	const [users, setUsers] = useState<User[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [busyId, setBusyId] = useState<string | null>(null);
	const [groupsRefresh, setGroupsRefresh] = useState(0);
	const [inviteOpen, setInviteOpen] = useState(false);
	const [inviting, setInviting] = useState(false);
	const [inviteError, setInviteError] = useState<string | null>(null);
	const [editingUser, setEditingUser] = useState<User | null>(null);
	const [editing, setEditing] = useState(false);
	const [editError, setEditError] = useState<string | null>(null);
	const [pendingDeleteUser, setPendingDeleteUser] = useState<User | null>(null);
	const [invitations, setInvitations] = useState<Invitation[]>([]);

	const currentUserId = session?.user.id;
	const adminCount = users.filter((user) => user.role === Role.Admin).length;
	const editingRoleLockedReason =
		editingUser?.id === currentUserId
			? '不能修改自己的角色。'
			: editingUser?.role === Role.Admin && adminCount <= 1
				? '不能把最后一个管理员改为只读用户。'
				: null;

	useEffect(() => {
		void Promise.all([usersApi.list(), invitationsApi.list()]).then(([listed, invited]) => {
			setUsers(listed.users);
			setError(listed.error ?? (invited.error ? (invited.message ?? null) : null));
			if (!invited.error) setInvitations(invited.invitations);
			setLoading(false);
		});
	}, []);

	const runAction = async (id: string, action: () => Promise<{ error?: unknown }>) => {
		setBusyId(id);
		setError(null);
		const actionResult = await action();
		if (actionResult.error) {
			setError(actionErrorMessage(actionResult.error, 'Action failed.'));
		} else {
			await invalidateOwners(queryClient);
		}
		const listed = await usersApi.list();
		setUsers(listed.users);
		if (listed.error) setError(listed.error);
		setGroupsRefresh((current) => current + 1);
		setBusyId(null);
	};

	const inviteUser = async ({ email, name, role }: InviteUserInput) => {
		setInviting(true);
		setInviteError(null);
		const result = await invitationsApi.create({ email, name, role });
		if (result.error) {
			setInviteError(result.message ?? '邀请用户失败。');
			setInviting(false);
			return;
		}
		setInviteOpen(false);
		setInviting(false);
		const [listed, invited] = await Promise.all([usersApi.list(), invitationsApi.list()]);
		setUsers(listed.users);
		if (listed.error) setError(listed.error);
		if (invited.error) setError(invited.message ?? '加载邀请失败。');
		else setInvitations(invited.invitations);
	};

	const editUser = async (user: User, input: UpdateUserInput) => {
		if (user.id === currentUserId && input.role !== user.role) {
			setEditError('不能修改自己的角色。');
			return;
		}
		if (user.role === Role.Admin && adminCount <= 1 && input.role !== Role.Admin) {
			setEditError('不能把最后一个管理员改为只读用户。');
			return;
		}
		setEditing(true);
		setEditError(null);
		const result = await usersApi.update(user.id, input);
		if (result.error) {
			setEditError(actionErrorMessage(result.error, '更新用户失败。'));
			setEditing(false);
			return;
		}
		await invalidateOwners(queryClient);
		const listed = await usersApi.list();
		if (listed.error) {
			setError(listed.error);
		} else {
			setUsers(listed.users);
		}
		setEditingUser(null);
		setEditing(false);
	};

	const deleteUser = (user: User) => {
		setPendingDeleteUser(user);
	};

	const confirmDeleteUser = async () => {
		if (!pendingDeleteUser) return;
		await runAction(pendingDeleteUser.id, () => usersApi.remove(pendingDeleteUser.id));
		setPendingDeleteUser(null);
	};

	const resetPassword = (user: User) => {
		void (async () => {
			setBusyId(user.id);
			setError(null);
			const result = await invitationsApi.resetPassword(user.id);
			if (result.error) {
				setError(result.message ?? '重置密码失败。');
				setBusyId(null);
				return;
			}
			const [listed, invited] = await Promise.all([usersApi.list(), invitationsApi.list()]);
			setUsers(listed.users);
			if (listed.error) setError(listed.error);
			if (invited.error) setError(invited.message ?? '加载邀请失败。');
			else setInvitations(invited.invitations);
			setBusyId(null);
		})();
	};

	const deleteInvitation = (invitation: Invitation) => {
		void (async () => {
			setBusyId(invitation.id);
			setError(null);
			const result = await invitationsApi.remove(invitation.id);
			if (result.error) {
				setError(result.message ?? '删除邀请失败。');
				setBusyId(null);
				return;
			}
			setInvitations((rows) => rows.filter((row) => row.id !== invitation.id));
			setBusyId(null);
		})();
	};

	const columns: TableColumn<User>[] = [
		{
			key: 'user',
			header: '用户',
			cell: (user) => (
				<div>
					<div className="font-medium">{user.name || '—'}</div>
					<div className="text-xs text-secondary">{user.email}</div>
				</div>
			),
		},
		{
			key: 'role',
			header: '角色',
			width: 'w-32',
			nowrap: true,
			cell: (user) => (user.role === Role.Admin ? '管理员' : '只读用户'),
		},
		{
			key: 'actions',
			header: '操作',
			width: 'w-16',
			nowrap: true,
			headerClassName: 'text-right',
			cell: (user) => {
				const isAdmin = user.role === Role.Admin;
				// Never let the last admin be demoted or deleted.
				const isLastAdmin = isAdmin && adminCount <= 1;
				const isSelf = currentUserId != null && user.id === currentUserId;
				const busy = busyId === user.id;
				return (
					<div className="flex justify-end">
						<PopoverMenu
							items={[
								{
									label: '编辑',
									icon: <Icon name={IconName.Pencil} className="h-3.5 w-3.5" />,
									onClick: () => {
										setEditError(null);
										setEditingUser(user);
									},
								},
								{
									label: '重置密码',
									icon: <Icon name={IconName.Key} className="h-3.5 w-3.5" />,
									onClick: () => resetPassword(user),
									disabled: isSelf,
								},
								{
									label: '删除',
									icon: <Icon name={IconName.Trash} className="h-3.5 w-3.5" />,
									onClick: () => void deleteUser(user),
									disabled: isLastAdmin,
									danger: true,
								},
							]}
							trigger={({ toggle }) => (
								<Button
									theme={ButtonTheme.IconNeutral}
									size={Size.SMALL}
									iconOnly
									type="button"
									disabled={busy}
									onClick={toggle}
									aria-label={`${user.name || user.email} 的操作`}
								>
									<Icon name={IconName.DotsVertical} className="h-4 w-4" />
								</Button>
							)}
						/>
					</div>
				);
			},
		},
	];

	const invitationColumns: TableColumn<Invitation>[] = [
		{
			key: 'email',
			header: '邮箱',
			cell: (invitation) => invitation.email,
		},
		{
			key: 'kind',
			header: '类型',
			width: 'w-36',
			nowrap: true,
			cell: (invitation) => invitationKindLabel[invitation.kind],
		},
		{
			key: 'role',
			header: '角色',
			width: 'w-28',
			nowrap: true,
			cell: (invitation) => (invitation.role === Role.Admin ? '管理员' : '只读用户'),
		},
		{
			key: 'status',
			header: '状态',
			width: 'w-28',
			nowrap: true,
			cell: (invitation) => invitationStatusLabel[invitation.status],
		},
		{
			key: 'expires',
			header: '过期时间',
			width: 'w-40',
			nowrap: true,
			cell: (invitation) => formatDate(invitation.expires_at, 'MMM DD YYYY HH:mm'),
		},
		{
			key: 'link',
			header: '链接',
			truncate: true,
			maxWidthClass: 'max-w-md',
			title: (invitation) => invitation.url ?? '',
			cell: (invitation) =>
				invitation.url ? (
					<div className="group flex min-w-0 items-center gap-1">
						<code
							className="min-w-0 truncate font-mono text-xs text-body dark:text-zinc-300"
							title={invitation.url}
						>
							{invitation.url}
						</code>
						<CopyButton text={invitation.url} className="shrink-0 opacity-100" />
					</div>
				) : (
					<span className="text-secondary">—</span>
				),
		},
		{
			key: 'actions',
			header: '操作',
			width: 'w-28',
			nowrap: true,
			headerClassName: 'text-right',
			cell: (invitation) => (
				<div className="flex justify-end">
					<Button
						theme={ButtonTheme.DangerOutline}
						size={Size.SMALL}
						type="button"
						disabled={busyId === invitation.id}
						onClick={() => deleteInvitation(invitation)}
					>
						删除
					</Button>
				</div>
			),
		},
	];

	return (
		<div className="h-full overflow-auto p-6">
			<div className="mx-auto max-w-6xl">
				<div className="mb-4">
					<h1 className="mb-1 text-lg font-semibold text-heading dark:text-zinc-100">
						用户
					</h1>
					<p className="text-xs text-secondary">
						管理员可以管理用户；只读用户可以查看其他页面并使用对话。
					</p>
				</div>

				{loading ? (
					<div role="status" aria-label="正在加载用户">
						<SkeletonTable columns={3} rows={8} />
					</div>
				) : (
					<Table
						columns={columns}
						rows={users}
						rowKey={(user) => user.id}
						layout="auto"
						emptyMessage="未找到用户"
					/>
				)}

				<GroupsSection users={users} usersLoading={loading} refreshToken={groupsRefresh} />

				<div className="mt-8">
					<div className="mb-3 flex items-start justify-between gap-4">
						<div className="min-w-0">
							<h2 className="mb-1 text-sm font-semibold text-heading dark:text-zinc-100">
								邀请
							</h2>
							<p className="text-xs text-secondary">
								按邮箱邀请。请自行复制链接并发送 ——
								对方通过链接设置密码。加入邀请会创建账号；重置邀请只修改密码。
							</p>
						</div>
						<Button
							theme={ButtonTheme.Primary}
							size={Size.SMALL}
							type="button"
							onClick={() => {
								setInviteError(null);
								setInviteOpen(true);
							}}
						>
							<Icon name={IconName.Plus} className="mr-1.5 h-4 w-4" />
							邀请
						</Button>
					</div>
					{loading ? (
						<div role="status" aria-label="正在加载邀请">
							<SkeletonTable columns={5} rows={4} />
						</div>
					) : (
						<Table
							columns={invitationColumns}
							rows={invitations}
							rowKey={(invitation) => invitation.id}
							layout="auto"
							emptyMessage="没有邀请"
						/>
					)}
				</div>
			</div>

			{inviteOpen ? (
				<InviteUserModal
					submitting={inviting}
					error={inviteError}
					onClose={() => setInviteOpen(false)}
					onInvite={(input) => {
						void inviteUser(input);
					}}
				/>
			) : null}

			{editingUser ? (
				<EditUserModal
					user={editingUser}
					roleLockedReason={editingRoleLockedReason}
					submitting={editing}
					error={editError}
					onClose={() => {
						if (!editing) setEditingUser(null);
					}}
					onEdit={(input) => {
						void editUser(editingUser, input);
					}}
				/>
			) : null}

			<ConfirmModal
				open={pendingDeleteUser !== null}
				title="删除用户"
				message={
					pendingDeleteUser == null
						? ''
						: `确定删除用户“${pendingDeleteUser.name || pendingDeleteUser.email}”吗？此操作会永久删除该账号及其数据。`
				}
				confirmLabel="删除"
				onConfirm={confirmDeleteUser}
				onCancel={() => {
					if (pendingDeleteUser == null || busyId !== pendingDeleteUser.id) {
						setPendingDeleteUser(null);
					}
				}}
				confirming={pendingDeleteUser != null && busyId === pendingDeleteUser.id}
			/>

			<Toast
				open={error !== null}
				message={error ?? ''}
				variant={ToastVariant.Error}
				onClose={() => setError(null)}
			/>
		</div>
	);
};
