// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Write chosen candidates to the glossary.
export const POST = withPermission({ acronym: ['create', 'update'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
