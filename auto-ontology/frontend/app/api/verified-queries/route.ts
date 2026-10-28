// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// List the verified-query library (reviewers).
export const GET = withPermission({ verifiedQuery: ['read'] })((req) => proxyToBackend(req));
// Add an entry directly, optionally certified (reviewers).
export const POST = withPermission({ verifiedQuery: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
