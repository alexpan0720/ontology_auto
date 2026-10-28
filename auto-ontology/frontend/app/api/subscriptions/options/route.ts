// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// What the subscription form picks from.
export const GET = withPermission({ subscription: ['read'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
