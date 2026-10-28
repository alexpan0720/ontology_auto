// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Grant a request by adding the requester to a group.
export const POST = withPermission({ accessRequest: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
