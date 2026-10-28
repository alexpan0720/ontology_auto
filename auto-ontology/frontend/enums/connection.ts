// SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Connector kinds supported in the new-connection wizard. */
export enum ConnectionType {
	DATABRICKS = 'databricks',
	POSTGRESQL = 'postgresql',
	MYSQL = 'mysql',
	SNOWFLAKE = 'snowflake',
	HEAVYDB = 'heavydb',
	KYUUBI = 'kyuubi',
	TRINO = 'trino',
	CLICKHOUSE = 'clickhouse',
}

export const connectionDisplayName: Record<ConnectionType, string> = {
	[ConnectionType.DATABRICKS]: 'Databricks',
	[ConnectionType.POSTGRESQL]: 'PostgreSQL',
	[ConnectionType.MYSQL]: 'MySQL',
	[ConnectionType.SNOWFLAKE]: 'Snowflake',
	[ConnectionType.HEAVYDB]: 'HeavyDB',
	[ConnectionType.KYUUBI]: 'Apache Kyuubi',
	[ConnectionType.TRINO]: 'Trino',
	[ConnectionType.CLICKHOUSE]: 'ClickHouse',
};

export const isConnectionType = (value: string | null | undefined): value is ConnectionType =>
	typeof value === 'string' && (Object.values(ConnectionType) as string[]).includes(value);

export type ConnectionFieldKey =
	| 'host'
	| 'http_path'
	| 'port'
	| 'account'
	| 'warehouse'
	| 'user'
	| 'password'
	| 'private_key'
	| 'private_key_passphrase'
	| 'database'
	| 'protocol'
	| 'ssa_url'
	| 'truststore'
	| 'truststore_file'
	| 'truststore_password'
	| 'schema'
	| 'http_scheme'
	| 'sso_federation'
	| 'table_allow_regex'
	| 'table_deny_regex';

export type ConnectionField = {
	key: ConnectionFieldKey;
	label: string;
	placeholder?: string;
	secret?: boolean;
	/** Optional fields are not required to enable Test/Create. */
	optional?: boolean;
	/** Sent with the connection test only; stripped before the connection is created. */
	testOnly?: boolean;
	/** Rendered as a checkbox and sent as a boolean rather than a string. */
	boolean?: boolean;
	/** Rendered as a textarea. Needed for pasted PEM keys, which span many lines. */
	multiline?: boolean;
	/** Rendered as a file picker; the value is the file's base64-encoded bytes. */
	file?: boolean;
	/** `accept` attribute for a file field. */
	fileAccept?: string;
	/** Helper text shown under the field. */
	hint?: string;
};

/**
 * Fields where supplying any one satisfies the requirement, so none of them can
 * be marked required on its own.
 *
 * Snowflake accounts that enforce MFA reject password sign-in for person users
 * and forbid passwords on service users, leaving a key pair as the only usable
 * credential. Accounts without that enforcement still take a password, so the
 * form has to accept either.
 */
export const CONNECTION_EITHER_FIELDS: Partial<Record<ConnectionType, ConnectionFieldKey[]>> = {
	[ConnectionType.SNOWFLAKE]: ['password', 'private_key'],
};

/** Form fields rendered per connector type. `database` is the connection identity. */
export const CONNECTION_FIELDS: Record<ConnectionType, ConnectionField[]> = {
	[ConnectionType.DATABRICKS]: [
		{
			key: 'host',
			label: '服务器主机名（Server Hostname）',
			placeholder: 'dbc-a1b2345c-d6e7.cloud.databricks.com',
		},
		{
			key: 'http_path',
			label: 'HTTP 路径（HTTP Path）',
			placeholder: '/sql/1.0/warehouses/a1b234c567d8e9fa',
		},
		{ key: 'password', label: '访问令牌（Access Token）', secret: true },
		{ key: 'database', label: 'Catalog（目录）', placeholder: 'main' },
		{
			key: 'schema',
			label: 'Schema',
			placeholder: '留空则从列表中选择',
			hint: '只导入此 schema。测试连接时会校验它是否存在，并跳过选择 schema 的步骤。留空则从列表中选择 schema。',
			optional: true,
			testOnly: true,
		},
		{
			key: 'sso_federation',
			label: '以当前登录用户身份认证（SSO）',
			hint: '对话中的查询将使用当前登录用户自己的 Databricks 权限，而不是上面的访问令牌。需要在 Databricks 中配置信任你 SSO 签发方的联合身份策略。数据导入始终使用访问令牌。',
			optional: true,
			boolean: true,
		},
	],
	[ConnectionType.POSTGRESQL]: [
		{ key: 'host', label: '主机', placeholder: 'localhost' },
		{ key: 'port', label: '端口', placeholder: '5432' },
		{ key: 'user', label: '用户', placeholder: 'postgres' },
		{ key: 'password', label: '密码', secret: true },
		{ key: 'database', label: '数据库', placeholder: 'my_database' },
	],
	[ConnectionType.MYSQL]: [
		{ key: 'host', label: '主机', placeholder: 'localhost' },
		{ key: 'port', label: '端口', placeholder: '3306', optional: true },
		{ key: 'user', label: '用户', placeholder: 'root' },
		{ key: 'password', label: '密码', secret: true },
		{ key: 'database', label: '数据库', placeholder: 'my_database' },
	],
	[ConnectionType.SNOWFLAKE]: [
		{ key: 'account', label: '账号', placeholder: 'xy12345.us-east-1' },
		{ key: 'warehouse', label: 'Warehouse（计算仓库）', placeholder: 'COMPUTE_WH' },
		{ key: 'user', label: '用户' },
		{
			key: 'password',
			label: '密码',
			secret: true,
			optional: true,
			hint: '如果账号强制启用了 MFA（会阻止无人值守服务用密码登录），请留空，并在下方粘贴私钥。',
		},
		{
			key: 'private_key',
			label: '私钥（PEM）',
			placeholder: '-----BEGIN PRIVATE KEY-----',
			secret: true,
			optional: true,
			multiline: true,
			hint: '密钥对认证。粘贴已在 Snowflake 用户上注册的私钥完整 PEM 内容，用于代替密码。',
		},
		{
			key: 'private_key_passphrase',
			label: '私钥口令',
			secret: true,
			optional: true,
			hint: '仅当上面的私钥已加密时需要填写。',
		},
		{ key: 'database', label: '数据库', placeholder: 'MY_DATABASE' },
	],
	[ConnectionType.HEAVYDB]: [
		{ key: 'host', label: '主机', placeholder: 'localhost' },
		{ key: 'port', label: '端口', placeholder: '6274', optional: true },
		{ key: 'user', label: '用户', placeholder: 'admin' },
		{ key: 'password', label: '密码', secret: true },
		{ key: 'database', label: '数据库', placeholder: 'heavyai' },
		{ key: 'protocol', label: '协议', placeholder: 'binary', optional: true },
	],
	[ConnectionType.KYUUBI]: [
		{ key: 'host', label: '主机' },
		{ key: 'port', label: '端口', optional: true },
		{
			key: 'user',
			label: '令牌生成客户端 ID',
			hint: '服务账号的 SSA 客户端 ID；如果直接粘贴令牌，则填写你的账号名。',
		},
		{
			key: 'password',
			label: '令牌生成客户端密钥',
			secret: true,
			hint: '如果下方填写了令牌生成地址，这里填 SSA 客户端密钥；否则填写从数据平台个人页面复制的 JWT。',
		},
		{
			key: 'ssa_url',
			label: '令牌生成地址',
			optional: true,
			hint: '启用服务账号认证。令牌每小时过期，填写后连接器会自动获取新令牌，避免一小时后失效。',
		},
		{ key: 'database', label: 'Catalog（目录）' },
		{
			key: 'truststore_file',
			label: '信任库（JKS）',
			file: true,
			fileAccept: '.jks,.keystore,.truststore',
			optional: true,
			hint: '上传 CA 信任库。当服务器尚未信任内部 CA 时需要。',
		},
		{
			key: 'truststore_password',
			label: '信任库密码',
			secret: true,
			optional: true,
		},
	],
	[ConnectionType.TRINO]: [
		{ key: 'host', label: '主机', placeholder: 'trino.example.com' },
		{ key: 'port', label: '端口', placeholder: '8080', optional: true },
		{
			key: 'user',
			label: '用户',
			placeholder: 'analyst',
			hint: '在无需认证的集群上，这只是 Trino 记录在查询上的身份标识。',
		},
		{
			key: 'password',
			label: '密码',
			secret: true,
			optional: true,
			hint: '集群无需认证时留空。填写密码后连接会切换为 HTTPS，因为 Trino 只在 HTTPS 下接受密码。',
		},
		{ key: 'database', label: 'Catalog（目录）', placeholder: 'hive' },
		{
			key: 'schema',
			label: 'Schema',
			placeholder: '留空则从列表中选择',
			hint: '只导入此 schema。留空则从列表中选择 schema。',
			optional: true,
		},
	],
	[ConnectionType.CLICKHOUSE]: [
		{
			key: 'host',
			label: '主机',
			placeholder: 'clickhouse.example.com',
			hint: '粘贴的 ClickHouse Cloud 地址可以带 https://，会按该协议连接。',
		},
		{
			key: 'port',
			label: '端口',
			placeholder: '8123',
			optional: true,
			hint: 'HTTP 接口端口：默认 8123，ClickHouse Cloud 为 8443。',
		},
		{
			key: 'user',
			label: '用户',
			placeholder: 'default',
			optional: true,
			hint: '留空则以服务器默认用户连接。',
		},
		{ key: 'password', label: '密码', secret: true, optional: true },
		{
			key: 'database',
			label: '数据库',
			placeholder: 'analytics',
			hint: 'ClickHouse 的数据库下没有 schema，一个连接只对应一个数据库。如需第二个数据库，请再添加一个连接。',
		},
		{
			key: 'http_scheme',
			label: '协议',
			placeholder: 'http',
			optional: true,
			hint: '留空则按端口推断：443 和 8443 用 https，其他端口用 http。其他端口上的 TLS 服务请显式填写 https —— 与 Trino 不同，这里仅填写密码不会自动启用 TLS。',
		},
	],
};

/**
 * Fields offered for every connector, appended after the type-specific ones.
 *
 * Kept separate rather than copied into all eight lists: they are enforced
 * centrally at catalog extraction (`auto_ontology/catalog/table_filter.py`), so
 * every connector honours them identically and none may drift.
 */
export const COMMON_CONNECTION_FIELDS: ConnectionField[] = [
	{
		key: 'table_allow_regex',
		label: '表白名单（正则）',
		placeholder: '留空则导入所有表',
		optional: true,
		hint: 'Ingest only tables whose name matches. Unanchored and case-sensitive, so "fact_" matches "fact_sales"; anchor with ^ and $ for an exact name.',
	},
	{
		key: 'table_deny_regex',
		label: '表黑名单（正则）',
		placeholder: '留空则不排除任何表',
		optional: true,
		hint: '跳过名称匹配的表，即使它也匹配白名单。适用于数据仓库能列出但实际无法读取的对象，例如损坏的 Distributed 表或 Kafka 队列。',
	},
];

/** Form fields for a connector: its own, plus the ones shared by all of them. */
export const connectionFieldsFor = (type: ConnectionType): ConnectionField[] => [
	...CONNECTION_FIELDS[type],
	...COMMON_CONNECTION_FIELDS,
];
