// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Replace a subscription's settings.
export const PUT = withPermission({ subscription: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);

// Delete a subscription and its history.
export const DELETE = withPermission({ subscription: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
