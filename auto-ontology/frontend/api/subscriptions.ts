// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithCount, ResponseWithError } from './types';
import type {
	PushChannel,
	PushPlatform,
	Subscription,
	SubscriptionFields,
	SubscriptionOptions,
	SubscriptionPreview,
	SubscriptionRun,
} from '@/types/subscriptions';

type Ok = ResponseWithError<{ ok: boolean }>;

export const pushChannelsApi = {
	list: (): Promise<ResponseWithError<ResponseWithCount<PushChannel[]>>> =>
		requests.get('push-channels'),
	create: (body: {
		name: string;
		platform: PushPlatform;
		webhook_url: string;
		secret?: string;
	}): Promise<ResponseWithError<{ id: string }>> => requests.post('push-channels', body),
	update: (
		id: string,
		body: { name?: string; webhook_url?: string; secret?: string; clear_secret?: boolean },
	): Promise<Ok> => requests.patch(`push-channels/${id}`, body),
	remove: (id: string): Promise<Ok> => requests.delete(`push-channels/${id}`),
	test: (body: {
		channel_id?: string;
		platform?: PushPlatform;
		webhook_url?: string;
		secret?: string;
	}): Promise<ResponseWithError<{ ok: boolean; message: string }>> =>
		requests.post('push-channels/test', body),
};

export const subscriptionsApi = {
	list: (): Promise<ResponseWithError<ResponseWithCount<Subscription[]>>> =>
		requests.get('subscriptions'),
	options: (): Promise<ResponseWithError<SubscriptionOptions>> =>
		requests.get('subscriptions/options'),
	create: (body: SubscriptionFields): Promise<ResponseWithError<{ id: string }>> =>
		requests.post('subscriptions', body),
	update: (id: string, body: SubscriptionFields): Promise<Ok> =>
		requests.put(`subscriptions/${id}`, body),
	remove: (id: string): Promise<Ok> => requests.delete(`subscriptions/${id}`),
	setEnabled: (id: string, enabled: boolean): Promise<Ok> =>
		requests.post(`subscriptions/${id}/enabled`, { enabled }),
	run: (id: string): Promise<ResponseWithError<SubscriptionRun>> =>
		requests.post(`subscriptions/${id}/run`, { trigger: 'manual' }),
	runs: (id: string): Promise<ResponseWithError<ResponseWithCount<SubscriptionRun[]>>> =>
		requests.get(`subscriptions/${id}/runs`),
	preview: (
		body: SubscriptionFields & { subscription_id?: string },
	): Promise<ResponseWithError<SubscriptionPreview>> =>
		requests.post('subscriptions/preview', body),
};
