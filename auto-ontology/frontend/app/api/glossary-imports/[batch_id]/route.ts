// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// One batch with its candidates.
export const GET = withPermission({ acronym: ['read'] })((req) => proxyToBackend(req));
// Delete a batch and its candidates; the glossary is not touched.
export const DELETE = withPermission({ acronym: ['delete'] })((req) => proxyToBackend(req));
