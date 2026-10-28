// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { requests } from './requests';
import type { ResponseWithCount, ResponseWithError } from './types';
import type { ApplyResult, GlossaryImport, GlossaryImportDetail } from '@/types/glossaryImport';

export const glossaryImportApi = {
	list: (): Promise<ResponseWithError<ResponseWithCount<GlossaryImport[]>>> =>
		requests.get('glossary-imports'),
	get: (id: string): Promise<ResponseWithError<GlossaryImportDetail>> =>
		requests.get(`glossary-imports/${id}`),
	upload: (file: File): Promise<ResponseWithError<{ id: string }>> => {
		const form = new FormData();
		form.append('file', file);
		return requests.postForm('glossary-imports', form);
	},
	remove: (id: string): Promise<ResponseWithError<{ ok: boolean }>> =>
		requests.delete(`glossary-imports/${id}`),
	updateCandidate: (
		id: string,
		changes: { term?: string; definition?: string; synonyms?: string[] },
	): Promise<ResponseWithError<{ ok: boolean }>> =>
		requests.patch(`glossary-candidates/${id}`, changes),
	apply: (
		id: string,
		body: { candidate_ids: string[]; overwrite_existing: boolean; update_terms: boolean },
	): Promise<ResponseWithError<ApplyResult>> =>
		requests.post(`glossary-imports/${id}/apply`, body),
	reject: (
		id: string,
		candidateIds: string[],
	): Promise<ResponseWithError<{ rejected: number }>> =>
		requests.post(`glossary-imports/${id}/reject`, { candidate_ids: candidateIds }),
};
