// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Mirrors `auto_ontology/server/objects/router.py`. */

export type ObjectStatus = 'candidate' | 'active';
export type LinkOrigin = 'foreign_key' | 'semantic_fk' | 'manual';

export type ObjectType = {
	id: string;
	table_id: string;
	display_name: string;
	description: string | null;
	pk_column: string;
	title_column: string | null;
	status: ObjectStatus;
	table_name: string;
	schema_name: string;
	database_name: string;
	created: string | null;
	modified: string | null;
	link_count: number;
};

export type ObjectLayerSummary = {
	active_types: number;
	candidate_types: number;
	active_links: number;
	candidate_links: number;
};

export type ObjectProperty = {
	column_name: string;
	/** The override, or a name derived from the column's description. */
	label: string;
	/** The override alone; null when none is stored. */
	display_name: string | null;
	hidden: boolean;
	description: string | null;
	data_type: string | null;
};

export type LinkTypeEnd = {
	id: string;
	display_name: string;
	status: ObjectStatus;
	table_name: string;
};

export type LinkType = {
	id: string;
	object_type_id: string;
	target_object_type_id: string;
	source_column: string;
	target_column: string;
	display_name: string;
	reverse_display_name: string;
	origin: LinkOrigin;
	status: ObjectStatus;
	source_type: LinkTypeEnd | null;
	target_type: LinkTypeEnd | null;
};

export type ObjectTypeDetail = Omit<ObjectType, 'link_count'> & {
	table_description: string | null;
	properties: ObjectProperty[];
	links: LinkType[];
};

export type ObjectTypeUpdate = {
	display_name?: string;
	description?: string | null;
	pk_column?: string;
	title_column?: string | null;
	status?: ObjectStatus;
	properties?: { column_name: string; display_name: string | null; hidden: boolean }[];
};

export type GenerateResult = { types: number; links: number; keyless_tables: string[] };

export type ObjectValue = string | number | boolean | null;

export type ObjectSummary = {
	key: string | null;
	title: string;
	values: Record<string, ObjectValue>;
};

export type ObjectPage = {
	columns: { name: string; label: string }[];
	objects: ObjectSummary[];
	has_more: boolean;
	pk_column: string;
	title_column: string;
};

export type LinkedObjects = {
	link_id: string;
	direction: 'out' | 'in';
	name: string;
	object_type: { id: string; display_name: string };
	/** Many on the reverse side of a link, at most one going forward. */
	many: boolean;
	objects: ObjectSummary[];
	has_more: boolean;
	error?: string;
};

export type ObjectDetail = ObjectSummary & {
	object_type: { id: string; display_name: string; description: string | null };
	properties: { name: string; label: string }[];
	links: LinkedObjects[];
};
