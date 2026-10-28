// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { z } from 'zod';
import { errorSchema } from '@/lib/openapiSchemas';
import type { OpenApiRoute } from '@/types/openapi';

export const openapi: OpenApiRoute = {
	put: {
		path: z.object({
			id: z.string().describe('Conversation id. Must belong to the caller.'),
			message_id: z.string().describe('An assistant message in that conversation.'),
		}),
		body: {
			description: 'Rate the answer, or clear the rating with `feedback: null`.',
			schema: z.object({
				feedback: z.enum(['up', 'down']).nullable(),
				note: z.string().optional().describe('What was wrong, for a `down` rating.'),
			}),
		},
		responses: {
			200: { description: 'Saved.', schema: z.object({ ok: z.boolean() }) },
			400: { description: 'An unknown rating.', schema: errorSchema },
			404: {
				description: 'No such assistant message in one of the caller’s conversations.',
				schema: errorSchema,
			},
		},
	},
};
