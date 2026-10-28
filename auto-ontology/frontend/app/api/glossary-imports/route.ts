// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// List import batches (glossary readers).
export const GET = withPermission({ acronym: ['read'] })((req) => proxyToBackend(req));
// Upload a document for extraction (glossary editors).
export const POST = withPermission({ acronym: ['create'] })((req, { user }) =>
	proxyToBackend(req, { userId: user.id }),
);
