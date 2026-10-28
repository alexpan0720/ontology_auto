// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Edit, certify or reject an entry (reviewers).
export const PATCH = withPermission({ verifiedQuery: ['manage'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
// Delete an entry (reviewers).
export const DELETE = withPermission({ verifiedQuery: ['manage'] })((req) => proxyToBackend(req));
