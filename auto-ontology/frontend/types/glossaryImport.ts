// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/server/glossary_import/router.py`. */

export type ImportStatus = 'processing' | 'done' | 'failed';
export type CandidateStatus = 'pending' | 'accepted' | 'rejected';

export type GlossaryImport = {
	id: string;
	file_name: string;
	status: ImportStatus;
	/** Why extraction failed (`error` is the response envelope's). */
	error_message: string | null;
	chunks_total: number;
	chunks_done: number;
	truncated: boolean;
	created: string | null;
	counts: Record<CandidateStatus, number>;
};

export type GlossaryCandidate = {
	id: string;
	term: string;
	definition: string;
	synonyms: string[];
	evidence: string | null;
	status: CandidateStatus;
	/** The glossary entry of the same name, if any — applying replaces it only on request. */
	existing_definition: string | null;
	/** A business term with this name or synonym, whose description can be updated too. */
	matched_term: { id: string; name: string; description: string | null } | null;
};

export type GlossaryImportDetail = Omit<GlossaryImport, 'counts'> & {
	candidates: GlossaryCandidate[];
};

export type ApplyResult = {
	added: number;
	replaced: number;
	skipped: number;
	terms_updated: number;
};
