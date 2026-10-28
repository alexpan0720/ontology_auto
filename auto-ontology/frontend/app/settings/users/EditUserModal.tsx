// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { useState } from 'react';
import { Button } from '@/common/Button';
import { Modal } from '@/common/modal';
import { Role } from '@/enums/auth';
import { Size, ButtonTheme } from '@/enums/button';
import type { UpdateUserInput, User } from '@/types/auth';

const inputClass =
	'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-heading outline-none focus:border-[#2563eb] focus:ring-1 focus:ring-[#2563eb] disabled:cursor-not-allowed disabled:bg-zinc-100 disabled:text-secondary dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:disabled:bg-zinc-800';

type EditUserModalProps = {
	user: User;
	roleLockedReason: string | null;
	submitting: boolean;
	error: string | null;
	onClose: () => void;
	onEdit: (input: UpdateUserInput) => void;
};

export const EditUserModal = ({
	user,
	roleLockedReason,
	submitting,
	error,
	onClose,
	onEdit,
}: EditUserModalProps) => {
	const [name, setName] = useState(user.name);
	const [role, setRole] = useState<Role>(user.role);

	return (
		<Modal open onClose={onClose} className="w-full max-w-md">
			<form
				className="space-y-4 p-5"
				onSubmit={(event) => {
					event.preventDefault();
					onEdit({ name: name.trim(), role });
				}}
			>
				<h2 className="text-sm font-semibold text-heading dark:text-zinc-100">编辑用户</h2>
				<p className="text-xs text-secondary dark:text-zinc-400">{user.email}</p>

				<label className="block space-y-1.5" htmlFor="edit-user-name">
					<span className="text-xs font-medium text-body dark:text-zinc-300">名称</span>
					<input
						id="edit-user-name"
						className={inputClass}
						type="text"
						required
						autoComplete="off"
						value={name}
						onChange={(event) => setName(event.target.value)}
					/>
				</label>

				<label className="block space-y-1.5" htmlFor="edit-user-role">
					<span className="text-xs font-medium text-body dark:text-zinc-300">角色</span>
					<select
						id="edit-user-role"
						className={inputClass}
						value={role}
						disabled={roleLockedReason !== null}
						onChange={(event) =>
							setRole(event.target.value === Role.Admin ? Role.Admin : Role.Viewer)
						}
					>
						<option value={Role.Viewer}>只读用户</option>
						<option value={Role.Admin}>管理员</option>
					</select>
				</label>

				{roleLockedReason ? (
					<p className="text-xs text-secondary">{roleLockedReason}</p>
				) : null}
				{error ? <p className="text-xs text-red-600 dark:text-red-400">{error}</p> : null}

				<div className="flex justify-end gap-2">
					<Button
						theme={ButtonTheme.Secondary}
						size={Size.SMALL}
						type="button"
						disabled={submitting}
						onClick={onClose}
					>
						取消
					</Button>
					<Button
						theme={ButtonTheme.Primary}
						size={Size.SMALL}
						type="submit"
						disabled={submitting || !name.trim()}
					>
						{submitting ? '保存中…' : '保存'}
					</Button>
				</div>
			</form>
		</Modal>
	);
};
