// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Class names shared by the settings and account pages built on cards and forms. */

export const PAGE_MAIN =
	'min-h-0 min-w-0 flex-1 overflow-y-auto bg-[linear-gradient(180deg,rgba(255,255,255,1)_0%,rgba(250,250,250,0.6)_100%)] px-7 py-6 sm:px-10 sm:py-7 dark:bg-[linear-gradient(180deg,rgba(9,9,11,1)_0%,rgba(24,24,27,0.5)_100%)]';

export const CARD =
	'rounded-lg border border-zinc-200/90 bg-white/90 p-5 shadow-sm ring-1 ring-zinc-950/[0.04] dark:border-zinc-700/90 dark:bg-zinc-950/50 dark:ring-white/[0.06]';

/** A denser card, for lists of many cards. */
export const CARD_COMPACT =
	'rounded-lg border border-zinc-200/90 bg-white/90 p-4 shadow-sm ring-1 ring-zinc-950/[0.04] dark:border-zinc-700/90 dark:bg-zinc-950/50 dark:ring-white/[0.06]';

export const INPUT =
	'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-body outline-none focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/20 disabled:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200';

/** For fields edited inline inside a list row. */
export const INPUT_DENSE =
	'w-full rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-body outline-none focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/20 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200';

/** A filter or search box in a toolbar, sized by its content. */
export const INPUT_FILTER =
	'rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-body outline-none focus:border-[#2563eb] dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200';

export const LABEL = 'flex flex-col gap-1 text-xs text-secondary dark:text-zinc-400';

export const PAGE_TITLE = 'text-base font-semibold text-heading dark:text-zinc-100';
export const PAGE_INTRO = 'mt-1 max-w-3xl text-xs text-secondary dark:text-zinc-400';
export const SECTION_TITLE = 'text-sm font-semibold text-heading dark:text-zinc-100';

export const BADGE = 'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium';
export const BADGE_TONE = {
	blue: 'bg-[#2563eb]/10 text-[#1e40af] dark:text-[#60a5fa]',
	green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
	amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
	red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
	grey: 'bg-zinc-100 text-secondary dark:bg-zinc-800 dark:text-zinc-400',
} as const;

export const NOTICE_OK = 'text-xs text-emerald-600 dark:text-emerald-400';
export const NOTICE_ERROR = 'text-xs text-red-600 dark:text-red-400';
