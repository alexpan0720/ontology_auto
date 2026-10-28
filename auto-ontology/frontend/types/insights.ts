// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/insights/board.py`. */

export type InsightCategory = 'downvoted' | 'error' | 'no_sql' | 'empty' | 'blocked';

export type InsightGroup = {
	key: string;
	question: string;
	count: number;
	category: InsightCategory;
	categories: Partial<Record<InsightCategory, number>>;
	users: number;
	sources: string[];
	last_seen: string;
	sql: string | null;
	detail: string | null;
	feedback_note: string | null;
};

export type InsightBoard = {
	days: number;
	totals: Record<InsightCategory, number> & {
		questions: number;
		answered: number;
		answer_rate: number | null;
	};
	groups: InsightGroup[];
};
