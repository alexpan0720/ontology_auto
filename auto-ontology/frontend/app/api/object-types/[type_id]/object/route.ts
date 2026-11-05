// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// One instance and what it links to.
export const GET = withPermission({ catalog: ['read'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id, forwardSubjectToken: true }),
);
