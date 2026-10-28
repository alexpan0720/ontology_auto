// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Restrict every PII-tagged column that has no policy yet (admins).
export const POST = withPermission({ accessPolicy: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
