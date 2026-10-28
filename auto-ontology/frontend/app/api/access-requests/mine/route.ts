// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// What the caller's policies keep from them, and their requests.
export const GET = withPermission({ accessRequest: ['submit'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
