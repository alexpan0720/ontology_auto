"""银行客户营销演示库的表结构：一处定义，生成建表语句与导入语句。

每张表、每个字段都带中文注释，并声明主键/外键（Unity Catalog 信息性约束）。
平台从这些注释和约束里推断业务含义、关联关系和业务对象，所以注释写的是业务口径，
不是技术说明。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Col:
    name: str
    type: str
    comment: str
    not_null: bool = False


@dataclass
class Table:
    name: str
    comment: str
    columns: list[Col]
    pk: list[str]
    fks: list[tuple[str, str, str]] = field(default_factory=list)  # (列, 引用表, 引用列)


TABLES: list[Table] = [
    Table(
        "dim_branch",
        "机构表：分行与支行，每行一个经营机构。支行通过上级机构归属到分行",
        [
            Col("branch_id", "BIGINT", "机构ID，主键", True),
            Col("branch_name", "STRING", "机构名称，如 上海陆家嘴支行"),
            Col("branch_level", "STRING", "机构层级：分行 / 支行"),
            Col("parent_branch_id", "BIGINT", "上级机构ID，支行指向所属分行，分行为空"),
            Col("city", "STRING", "所在城市"),
            Col("region", "STRING", "所属区域：华东 / 华北 / 华南 / 西南"),
            Col("open_date", "DATE", "机构开业日期"),
        ],
        ["branch_id"],
        [("parent_branch_id", "dim_branch", "branch_id")],
    ),
    Table(
        "dim_relationship_manager",
        "客户经理表：零售客户经理，含支行理财经理和分行私行客户经理",
        [
            Col("rm_id", "BIGINT", "客户经理ID，主键", True),
            Col("rm_name", "STRING", "客户经理姓名"),
            Col("branch_id", "BIGINT", "所属机构ID"),
            Col("rm_level", "STRING", "客户经理职级：初级 / 中级 / 高级 / 资深客户经理 / 私行客户经理"),
            Col("hire_date", "DATE", "入职日期"),
            Col("mobile", "STRING", "工作手机号"),
            Col("status", "STRING", "在岗状态：在岗 / 离职"),
        ],
        ["rm_id"],
        [("branch_id", "dim_branch", "branch_id")],
    ),
    Table(
        "dim_product",
        "产品表：零售在售和历史产品，涵盖存款、大额存单、理财、基金、保险、贵金属、信用卡和个人贷款",
        [
            Col("product_id", "BIGINT", "产品ID，主键", True),
            Col("product_name", "STRING", "产品名称"),
            Col("product_type", "STRING", "产品大类：活期存款 / 定期存款 / 大额存单 / 理财产品 / 公募基金 / 保险 / 贵金属 / 信用卡 / 个人贷款"),
            Col("risk_rating", "STRING", "产品风险等级：R1（低）到 R5（高），销售时须不高于客户风险测评等级"),
            Col("term_days", "INT", "产品期限（天），0 表示无固定期限或随时申赎"),
            Col("expected_yield", "DECIMAL(8,4)", "业绩比较基准或年利率，小数表示，如 0.0175 即 1.75%；权益类产品为空"),
            Col("min_amount", "DECIMAL(18,2)", "起购金额（元）"),
            Col("launch_date", "DATE", "上市日期"),
            Col("status", "STRING", "销售状态：在售 / 停售"),
        ],
        ["product_id"],
    ),
    Table(
        "dim_customer",
        "零售客户表：每行一个个人客户，含基本信息、客户等级、风险测评与管户客户经理",
        [
            Col("customer_id", "BIGINT", "客户号，主键", True),
            Col("customer_name", "STRING", "客户姓名"),
            Col("gender", "STRING", "性别：男 / 女"),
            Col("birth_date", "DATE", "出生日期"),
            Col("id_card_no", "STRING", "居民身份证号（敏感信息）"),
            Col("mobile", "STRING", "手机号（敏感信息）"),
            Col("city", "STRING", "所在城市"),
            Col("branch_id", "BIGINT", "开户机构ID（归属支行）"),
            Col("rm_id", "BIGINT", "管户客户经理ID，未分配管户时为空"),
            Col("open_date", "DATE", "开户日期"),
            Col("customer_level", "STRING", "客户等级，按月末AUM划分：普通（<5万）/ 金卡（5万-50万）/ 白金（50万-200万）/ 钻石（200万-600万）/ 私行（≥600万）"),
            Col("occupation", "STRING", "职业"),
            Col("annual_income_band", "STRING", "年收入区间"),
            Col("risk_level", "STRING", "风险测评等级：C1 保守型 / C2 稳健型 / C3 平衡型 / C4 成长型 / C5 进取型"),
            Col("risk_assess_date", "DATE", "最近一次风险测评日期，超过一年视为过期"),
            Col("is_payroll", "BOOLEAN", "是否代发工资客户"),
            Col("preferred_channel", "STRING", "偏好服务渠道：手机银行 / 网点柜面 / 客户经理 / 微信银行"),
            Col("marketing_consent", "BOOLEAN", "是否同意接收营销信息，不同意的客户不得纳入营销名单"),
            Col("customer_status", "STRING", "客户状态：正常 / 沉睡（长期无交易、资产极低）"),
        ],
        ["customer_id"],
        [("branch_id", "dim_branch", "branch_id"), ("rm_id", "dim_relationship_manager", "rm_id")],
    ),
    Table(
        "dim_customer_tag_def",
        "客户标签定义表：营销用客户标签的编码、名称和打标规则",
        [
            Col("tag_code", "STRING", "标签编码，主键", True),
            Col("tag_name", "STRING", "标签名称"),
            Col("tag_rule", "STRING", "打标规则说明"),
        ],
        ["tag_code"],
    ),
    Table(
        "fact_account",
        "账户表：客户的借记卡、II类电子账户和信用卡账户",
        [
            Col("account_id", "BIGINT", "账户号，主键", True),
            Col("customer_id", "BIGINT", "客户号"),
            Col("account_type", "STRING", "账户类型：I类借记卡 / II类电子账户 / 信用卡"),
            Col("open_date", "DATE", "开户日期"),
            Col("branch_id", "BIGINT", "开户机构ID"),
            Col("account_status", "STRING", "账户状态：正常 / 久悬 / 销户"),
        ],
        ["account_id"],
        [("customer_id", "dim_customer", "customer_id"), ("branch_id", "dim_branch", "branch_id")],
    ),
    Table(
        "fact_aum_monthly",
        "客户月末资产快照：每个客户每月末一行。AUM（管理资产）= 活期 + 定期（含大额存单）+ 理财 + 基金 + 保险现金价值，不含贷款",
        [
            Col("snapshot_month", "DATE", "快照日期，为当月最后一天", True),
            Col("customer_id", "BIGINT", "客户号", True),
            Col("demand_deposit", "DECIMAL(18,2)", "活期存款余额（元）"),
            Col("time_deposit", "DECIMAL(18,2)", "定期存款余额（元），含大额存单"),
            Col("wealth_balance", "DECIMAL(18,2)", "理财产品余额（元）"),
            Col("fund_balance", "DECIMAL(18,2)", "公募基金市值（元）"),
            Col("insurance_value", "DECIMAL(18,2)", "代销保险现金价值（元）"),
            Col("total_aum", "DECIMAL(18,2)", "AUM 管理资产合计（元）"),
            Col("loan_balance", "DECIMAL(18,2)", "个人贷款余额（元），不计入AUM"),
        ],
        ["snapshot_month", "customer_id"],
        [("customer_id", "dim_customer", "customer_id")],
    ),
    Table(
        "fact_holding",
        "客户持仓表：客户持有或曾经持有的定期、大额存单、理财、基金和保险",
        [
            Col("holding_id", "BIGINT", "持仓ID，主键", True),
            Col("customer_id", "BIGINT", "客户号"),
            Col("product_id", "BIGINT", "产品ID"),
            Col("buy_date", "DATE", "购买（起息）日期"),
            Col("maturity_date", "DATE", "到期日期，无固定期限产品为空"),
            Col("holding_amount", "DECIMAL(18,2)", "持有金额（元）"),
            Col("holding_status", "STRING", "持仓状态：持有中 / 已到期 / 已赎回"),
        ],
        ["holding_id"],
        [("customer_id", "dim_customer", "customer_id"), ("product_id", "dim_product", "product_id")],
    ),
    Table(
        "fact_transaction",
        "交易流水表：最近12个月客户借记卡的资金交易",
        [
            Col("txn_id", "BIGINT", "交易流水号，主键", True),
            Col("account_id", "BIGINT", "账户号"),
            Col("customer_id", "BIGINT", "客户号"),
            Col("txn_time", "TIMESTAMP", "交易时间"),
            Col("txn_type", "STRING", "交易类型：消费 / 转入 / 转出至本行 / 转出至他行 / 代发工资入账 / 理财申购 / 理财赎回 / 基金申购 / 取现 / 还款"),
            Col("direction", "STRING", "资金方向：收入 / 支出"),
            Col("channel", "STRING", "交易渠道：手机银行 / 网上银行 / 柜面 / ATM / POS / 第三方支付 / 批量代发"),
            Col("amount", "DECIMAL(18,2)", "交易金额（元）"),
            Col("counterparty", "STRING", "交易对手类型或消费商户类别，如 他行、本行、餐饮、商超"),
        ],
        ["txn_id"],
        [("account_id", "fact_account", "account_id"), ("customer_id", "dim_customer", "customer_id")],
    ),
    Table(
        "mkt_campaign",
        "营销活动表：零售营销活动，如揽储、理财销售、基金定投、信用卡获客、流失挽回和到期承接",
        [
            Col("campaign_id", "BIGINT", "营销活动ID，主键", True),
            Col("campaign_name", "STRING", "活动名称"),
            Col("campaign_type", "STRING", "活动类型：存款揽储 / 理财销售 / 基金定投 / 保险销售 / 信用卡获客 / 贷款营销 / 客户促活 / 流失挽回 / 到期承接 / 客户关怀"),
            Col("target_product_type", "STRING", "主推产品大类"),
            Col("start_date", "DATE", "活动开始日期"),
            Col("end_date", "DATE", "活动结束日期"),
            Col("main_channel", "STRING", "主要触达渠道：客户经理面访 / 外呼 / 微信 / APP推送 / 短信"),
            Col("target_rule", "STRING", "目标客群筛选规则"),
            Col("budget", "DECIMAL(18,2)", "活动预算（元）"),
            Col("owner_branch_id", "BIGINT", "牵头分行ID，总行统一组织的活动为空"),
            Col("campaign_status", "STRING", "活动状态：已结束 / 进行中 / 未开始"),
        ],
        ["campaign_id"],
        [("owner_branch_id", "dim_branch", "branch_id")],
    ),
    Table(
        "mkt_campaign_target",
        "营销名单与触达记录：每行一个被纳入活动名单的客户及其触达结果",
        [
            Col("target_id", "BIGINT", "名单记录ID，主键", True),
            Col("campaign_id", "BIGINT", "营销活动ID"),
            Col("customer_id", "BIGINT", "客户号"),
            Col("rm_id", "BIGINT", "跟进客户经理ID，非人工渠道为空"),
            Col("assign_date", "DATE", "入单（下发）日期"),
            Col("contact_channel", "STRING", "触达渠道"),
            Col("contact_time", "TIMESTAMP", "触达时间，未触达为空"),
            Col("contact_result", "STRING", "触达结果：未触达 / 已触达未响应 / 有意向 / 明确拒绝 / 已成交"),
        ],
        ["target_id"],
        [("campaign_id", "mkt_campaign", "campaign_id"), ("customer_id", "dim_customer", "customer_id"), ("rm_id", "dim_relationship_manager", "rm_id")],
    ),
    Table(
        "mkt_conversion",
        "营销成交表：营销名单中成交的业务，记录成交产品、金额和中间业务收入",
        [
            Col("conversion_id", "BIGINT", "成交记录ID，主键", True),
            Col("target_id", "BIGINT", "对应的名单记录ID"),
            Col("campaign_id", "BIGINT", "营销活动ID"),
            Col("customer_id", "BIGINT", "客户号"),
            Col("product_id", "BIGINT", "成交产品ID"),
            Col("convert_date", "DATE", "成交日期"),
            Col("convert_amount", "DECIMAL(18,2)", "成交金额（元），信用卡为0"),
            Col("fee_income", "DECIMAL(18,2)", "中间业务收入（元），如理财、基金、保险的销售手续费"),
            Col("rm_id", "BIGINT", "业绩归属客户经理ID"),
        ],
        ["conversion_id"],
        [
            ("target_id", "mkt_campaign_target", "target_id"),
            ("campaign_id", "mkt_campaign", "campaign_id"),
            ("customer_id", "dim_customer", "customer_id"),
            ("product_id", "dim_product", "product_id"),
            ("rm_id", "dim_relationship_manager", "rm_id"),
        ],
    ),
    Table(
        "fact_customer_event",
        "客户事件表（营销商机）：到期、大额资金转出、资产下滑、代发停发、生日等需要客户经理跟进的事件",
        [
            Col("event_id", "BIGINT", "事件ID，主键", True),
            Col("customer_id", "BIGINT", "客户号"),
            Col("event_type", "STRING", "事件类型：定期到期 / 理财到期 / 大额资金转出 / 资产下滑 / 代发停发 / 客户生日"),
            Col("event_date", "DATE", "事件日期（到期类为到期日）"),
            Col("related_amount", "DECIMAL(18,2)", "涉及金额（元）"),
            Col("detail", "STRING", "事件说明"),
            Col("handle_status", "STRING", "跟进状态：待跟进 / 已跟进"),
        ],
        ["event_id"],
        [("customer_id", "dim_customer", "customer_id")],
    ),
    Table(
        "fact_customer_tag",
        "客户标签表：每行一个客户命中的一个营销标签",
        [
            Col("customer_id", "BIGINT", "客户号", True),
            Col("tag_code", "STRING", "标签编码", True),
            Col("tag_name", "STRING", "标签名称"),
            Col("score", "DECIMAL(6,2)", "标签强度得分，0-100"),
            Col("tag_date", "DATE", "打标日期"),
        ],
        ["customer_id", "tag_code"],
        [("customer_id", "dim_customer", "customer_id"), ("tag_code", "dim_customer_tag_def", "tag_code")],
    ),
]

SCHEMA_COMMENT = "零售银行客户营销演示数据：客户、资产、持仓、交易、营销活动与商机"


def create_table_sql(table: Table) -> str:
    cols = [
        f"  {c.name} {c.type}{' NOT NULL' if c.not_null or c.name in table.pk else ''} COMMENT '{c.comment}'"
        for c in table.columns
    ]
    cols.append(f"  CONSTRAINT pk_{table.name} PRIMARY KEY ({', '.join(table.pk)})")
    return f"CREATE TABLE {table.name} (\n" + ",\n".join(cols) + f"\n) COMMENT '{table.comment}'"


def foreign_key_sql(table: Table) -> list[str]:
    return [
        f"ALTER TABLE {table.name} ADD CONSTRAINT fk_{table.name}_{col} FOREIGN KEY ({col}) REFERENCES {ref}({ref_col})"
        for col, ref, ref_col in table.fks
    ]


def insert_sql(table: Table, source: str) -> str:
    select = ", ".join(f"CAST({c.name} AS {c.type}) AS {c.name}" for c in table.columns)
    return f"INSERT INTO {table.name} SELECT {select} FROM {source}"


def full_script(catalog: str, schema: str) -> str:
    """The DDL as one script, for reading or running by hand in the SQL editor."""
    parts = [f"USE CATALOG {catalog}", f"CREATE SCHEMA IF NOT EXISTS {schema} COMMENT '{SCHEMA_COMMENT}'", f"USE SCHEMA {schema}"]
    parts += [f"DROP TABLE IF EXISTS {t.name}" for t in reversed(TABLES)]
    parts += [create_table_sql(t) for t in TABLES]
    parts += [sql for t in TABLES for sql in foreign_key_sql(t)]
    return ";\n\n".join(parts) + ";\n"


if __name__ == "__main__":
    print(full_script("workspace", "bank_marketing"))
