// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithCount, ResponseWithError } from './types';
import type {
	GenerateResult,
	ObjectDetail,
	ObjectLayerSummary,
	ObjectPage,
	ObjectStatus,
	ObjectType,
	ObjectTypeDetail,
	ObjectTypeUpdate,
} from '@/types/objects';

type Ok = ResponseWithError<{ ok: boolean }>;

export const objectTypesApi = {
	list: (
		status?: ObjectStatus,
	): Promise<
		ResponseWithError<ResponseWithCount<ObjectType[]> & { summary: ObjectLayerSummary }>
	> => requests.get('object-types', status ? { status } : undefined),
	get: (id: string): Promise<ResponseWithError<ObjectTypeDetail>> =>
		requests.get(`object-types/${id}`),
	generate: (): Promise<ResponseWithError<GenerateResult>> =>
		requests.post('object-types/generate', {}),
	create: (body: {
		table_id: string;
		display_name?: string;
		pk_column?: string;
	}): Promise<ResponseWithError<{ id: string }>> => requests.post('object-types', body),
	update: (id: string, body: ObjectTypeUpdate): Promise<Ok> =>
		requests.patch(`object-types/${id}`, body),
	remove: (id: string): Promise<Ok> => requests.delete(`object-types/${id}`),
	bulk: (
		ids: string[],
		action: 'accept' | 'delete',
	): Promise<ResponseWithError<{ types: number; links: number }>> =>
		requests.post('object-types/bulk', { ids, action }),
	objects: (
		id: string,
		params: { search?: string; limit?: number; offset?: number },
	): Promise<ResponseWithError<ObjectPage>> => requests.get(`object-types/${id}/objects`, params),
	object: (id: string, key: string): Promise<ResponseWithError<ObjectDetail>> =>
		requests.get(`object-types/${id}/object`, { key }),
};

export const linkTypesApi = {
	create: (body: {
		object_type_id: string;
		source_column: string;
		target_object_type_id: string;
		target_column?: string;
		display_name?: string;
		reverse_display_name?: string;
	}): Promise<ResponseWithError<{ id: string }>> => requests.post('link-types', body),
	update: (
		id: string,
		body: { display_name?: string; reverse_display_name?: string; status?: ObjectStatus },
	): Promise<Ok> => requests.patch(`link-types/${id}`, body),
	remove: (id: string): Promise<Ok> => requests.delete(`link-types/${id}`),
};
