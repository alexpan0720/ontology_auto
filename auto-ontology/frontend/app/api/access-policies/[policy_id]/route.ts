// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { withPermission } from '@/auth/with-auth';
import { proxyToBackend } from '@/auth/proxy-backend';

// Edit or delete one access policy (admins).
export const PATCH = withPermission({ accessPolicy: ['manage'] })((req) => proxyToBackend(req));
export const DELETE = withPermission({ accessPolicy: ['manage'] })((req) => proxyToBackend(req));
