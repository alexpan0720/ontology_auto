// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export type BotPlatform = 'dingtalk' | 'feishu';

/** Mirrors `auto_ontology/bots/config.public`: the secret itself never comes back. */
export type BotSettings = {
	platform: BotPlatform;
	enabled: boolean;
	app_id: string;
	has_secret: boolean;
	status: 'connected' | 'error' | 'stopped' | null;
	status_detail: string | null;
	status_updated: string | null;
};
