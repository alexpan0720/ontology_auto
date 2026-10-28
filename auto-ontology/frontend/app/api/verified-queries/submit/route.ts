// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Submit a question/SQL pair from answer feedback for review (any user).
export const POST = withPermission({ verifiedQuery: ['submit'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
