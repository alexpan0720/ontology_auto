// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Every subscription with its last run.
export const GET = withPermission({ subscription: ['read'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);

// Create a subscription.
export const POST = withPermission({ subscription: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
