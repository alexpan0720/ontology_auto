// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Every access request, for reviewers.
export const GET = withPermission({ accessRequest: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);

// Ask for a field or rows a policy keeps from the caller.
export const POST = withPermission({ accessRequest: ['submit'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
