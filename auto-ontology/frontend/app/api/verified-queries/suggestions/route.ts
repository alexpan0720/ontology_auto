// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Certified questions as starting points, question text only: anyone who may
// ask may see them, unlike the library itself, which carries the SQL.
export const GET = withPermission({ chat: ['use'] })((req) => proxyToBackend(req));
