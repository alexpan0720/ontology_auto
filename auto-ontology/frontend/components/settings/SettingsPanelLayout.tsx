// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

'use client';

import { type ReactNode } from 'react';
import { BackPanelLayout } from '@/common/BackPanelLayout';
import { SettingsNav } from '@/components/settings/SettingsNav';

type SettingsPanelLayoutProps = {
	children: ReactNode;
	/** Passed straight to the nav, which drops Connections when it is set. */
	connectionsEnvManaged: boolean;
};

export const SettingsPanelLayout = ({
	children,
	connectionsEnvManaged,
}: SettingsPanelLayoutProps) => (
	<BackPanelLayout
		panelAriaLabel="设置分类"
		expandAriaLabel="展开设置菜单"
		collapseAriaLabel="收起设置菜单"
		panel={<SettingsNav connectionsEnvManaged={connectionsEnvManaged} />}
	>
		{children}
	</BackPanelLayout>
);
