// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { SettingsOverview } from '@/components/settings/SettingsOverview';
import { readConnectionsEnvSource } from '@/lib/server/connections';

// The admin centre's landing page. It used to redirect straight into
// Connections, which told a new admin nothing about what else was here.
export default async function SettingsPage() {
	const envManaged = await readConnectionsEnvSource();
	return <SettingsOverview connectionsEnvManaged={envManaged === true} />;
}
