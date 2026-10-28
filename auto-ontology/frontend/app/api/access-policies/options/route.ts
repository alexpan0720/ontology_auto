// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Tables, their columns and the user groups a policy can target (admins).
export const GET = withPermission({ accessPolicy: ['read'] })((req) => proxyToBackend(req));
