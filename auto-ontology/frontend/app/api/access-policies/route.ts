// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// List access policies (admins).
export const GET = withPermission({ accessPolicy: ['read'] })((req) => proxyToBackend(req));
// Create a column or row policy (admins).
export const POST = withPermission({ accessPolicy: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
