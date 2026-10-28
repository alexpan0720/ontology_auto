// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { NextResponse } from 'next/server';
import { getPrisma } from '@/lib/prisma';
import { withPermission } from '@/auth/with-auth';

type Ctx = { params: Promise<{ id: string; message_id: string }> };

const RATINGS = new Set(['up', 'down']);

// Rate an assistant answer in a conversation the caller owns. `feedback: null`
// clears the rating. 404 when the message is not an assistant answer in one of
// the caller's conversations, so another user's ids are indistinguishable from
// missing ones.
export const PUT = withPermission<Ctx>({ conversation: ['write'] })(async (
	req,
	{ params, user },
) => {
	const prisma = getPrisma();
	const { id, message_id: messageId } = await params;
	const body = (await req.json().catch(() => null)) as {
		feedback?: unknown;
		note?: unknown;
	} | null;

	const feedback = body?.feedback ?? null;
	if (feedback !== null && (typeof feedback !== 'string' || !RATINGS.has(feedback))) {
		return NextResponse.json(
			{ error: 'feedback must be "up", "down" or null' },
			{ status: 400 },
		);
	}
	const note = typeof body?.note === 'string' ? body.note.trim().slice(0, 2000) || null : null;

	const updated = await prisma.message.updateMany({
		where: {
			id: messageId,
			conversation_id: id,
			role: 'assistant',
			conversation: { user_id: user.id },
		},
		data: { feedback, feedback_note: feedback === null ? null : note },
	});
	if (updated.count === 0) {
		return NextResponse.json({ error: 'Message not found' }, { status: 404 });
	}
	return NextResponse.json({ ok: true });
});
