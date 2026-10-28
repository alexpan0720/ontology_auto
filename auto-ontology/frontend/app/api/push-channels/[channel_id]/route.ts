// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Rename a channel or replace its webhook / secret.
export const PATCH = withPermission({ subscription: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);

// Delete a channel.
export const DELETE = withPermission({ subscription: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
