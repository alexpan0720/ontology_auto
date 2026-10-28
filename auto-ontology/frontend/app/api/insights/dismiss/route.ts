// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Mark a failed question handled.
export const POST = withPermission({ insight: ['read'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
