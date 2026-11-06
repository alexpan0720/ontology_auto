USE CATALOG workspace;

CREATE SCHEMA IF NOT EXISTS bank_marketing COMMENT '零售银行客户营销演示数据：客户、资产、持仓、交易、营销活动与商机';

USE SCHEMA bank_marketing;

DROP TABLE IF EXISTS fact_customer_tag;

DROP TABLE IF EXISTS fact_customer_event;

DROP TABLE IF EXISTS mkt_conversion;

DROP TABLE IF EXISTS mkt_campaign_target;

DROP TABLE IF EXISTS mkt_campaign;

DROP TABLE IF EXISTS fact_transaction;

DROP TABLE IF EXISTS fact_holding;

DROP TABLE IF EXISTS fact_aum_monthly;

DROP TABLE IF EXISTS fact_account;

DROP TABLE IF EXISTS dim_customer_tag_def;

DROP TABLE IF EXISTS dim_customer;

DROP TABLE IF EXISTS dim_product;

DROP TABLE IF EXISTS dim_relationship_manager;

DROP TABLE IF EXISTS dim_branch;

CREATE TABLE dim_branch (
  branch_id BIGINT NOT NULL COMMENT '机构ID，主键',
  branch_name STRING COMMENT '机构名称，如 上海陆家嘴支行',
  branch_level STRING COMMENT '机构层级：分行 / 支行',
  parent_branch_id BIGINT COMMENT '上级机构ID，支行指向所属分行，分行为空',
  city STRING COMMENT '所在城市',
  region STRING COMMENT '所属区域：华东 / 华北 / 华南 / 西南',
  open_date DATE COMMENT '机构开业日期',
  CONSTRAINT pk_dim_branch PRIMARY KEY (branch_id)
) COMMENT '机构表：分行与支行，每行一个经营机构。支行通过上级机构归属到分行';

CREATE TABLE dim_relationship_manager (
  rm_id BIGINT NOT NULL COMMENT '客户经理ID，主键',
  rm_name STRING COMMENT '客户经理姓名',
  branch_id BIGINT COMMENT '所属机构ID',
  rm_level STRING COMMENT '客户经理职级：初级 / 中级 / 高级 / 资深客户经理 / 私行客户经理',
  hire_date DATE COMMENT '入职日期',
  mobile STRING COMMENT '工作手机号',
  status STRING COMMENT '在岗状态：在岗 / 离职',
  CONSTRAINT pk_dim_relationship_manager PRIMARY KEY (rm_id)
) COMMENT '客户经理表：零售客户经理，含支行理财经理和分行私行客户经理';

CREATE TABLE dim_product (
  product_id BIGINT NOT NULL COMMENT '产品ID，主键',
  product_name STRING COMMENT '产品名称',
  product_type STRING COMMENT '产品大类：活期存款 / 定期存款 / 大额存单 / 理财产品 / 公募基金 / 保险 / 贵金属 / 信用卡 / 个人贷款',
  risk_rating STRING COMMENT '产品风险等级：R1（低）到 R5（高），销售时须不高于客户风险测评等级',
  term_days INT COMMENT '产品期限（天），0 表示无固定期限或随时申赎',
  expected_yield DECIMAL(8,4) COMMENT '业绩比较基准或年利率，小数表示，如 0.0175 即 1.75%；权益类产品为空',
  min_amount DECIMAL(18,2) COMMENT '起购金额（元）',
  launch_date DATE COMMENT '上市日期',
  status STRING COMMENT '销售状态：在售 / 停售',
  CONSTRAINT pk_dim_product PRIMARY KEY (product_id)
) COMMENT '产品表：零售在售和历史产品，涵盖存款、大额存单、理财、基金、保险、贵金属、信用卡和个人贷款';

CREATE TABLE dim_customer (
  customer_id BIGINT NOT NULL COMMENT '客户号，主键',
  customer_name STRING COMMENT '客户姓名',
  gender STRING COMMENT '性别：男 / 女',
  birth_date DATE COMMENT '出生日期',
  id_card_no STRING COMMENT '居民身份证号（敏感信息）',
  mobile STRING COMMENT '手机号（敏感信息）',
  city STRING COMMENT '所在城市',
  branch_id BIGINT COMMENT '开户机构ID（归属支行）',
  rm_id BIGINT COMMENT '管户客户经理ID，未分配管户时为空',
  open_date DATE COMMENT '开户日期',
  customer_level STRING COMMENT '客户等级，按月末AUM划分：普通（<5万）/ 金卡（5万-50万）/ 白金（50万-200万）/ 钻石（200万-600万）/ 私行（≥600万）',
  occupation STRING COMMENT '职业',
  annual_income_band STRING COMMENT '年收入区间',
  risk_level STRING COMMENT '风险测评等级：C1 保守型 / C2 稳健型 / C3 平衡型 / C4 成长型 / C5 进取型',
  risk_assess_date DATE COMMENT '最近一次风险测评日期，超过一年视为过期',
  is_payroll BOOLEAN COMMENT '是否代发工资客户',
  preferred_channel STRING COMMENT '偏好服务渠道：手机银行 / 网点柜面 / 客户经理 / 微信银行',
  marketing_consent BOOLEAN COMMENT '是否同意接收营销信息，不同意的客户不得纳入营销名单',
  customer_status STRING COMMENT '客户状态：正常 / 沉睡（长期无交易、资产极低）',
  CONSTRAINT pk_dim_customer PRIMARY KEY (customer_id)
) COMMENT '零售客户表：每行一个个人客户，含基本信息、客户等级、风险测评与管户客户经理';

CREATE TABLE dim_customer_tag_def (
  tag_code STRING NOT NULL COMMENT '标签编码，主键',
  tag_name STRING COMMENT '标签名称',
  tag_rule STRING COMMENT '打标规则说明',
  CONSTRAINT pk_dim_customer_tag_def PRIMARY KEY (tag_code)
) COMMENT '客户标签定义表：营销用客户标签的编码、名称和打标规则';

CREATE TABLE fact_account (
  account_id BIGINT NOT NULL COMMENT '账户号，主键',
  customer_id BIGINT COMMENT '客户号',
  account_type STRING COMMENT '账户类型：I类借记卡 / II类电子账户 / 信用卡',
  open_date DATE COMMENT '开户日期',
  branch_id BIGINT COMMENT '开户机构ID',
  account_status STRING COMMENT '账户状态：正常 / 久悬 / 销户',
  CONSTRAINT pk_fact_account PRIMARY KEY (account_id)
) COMMENT '账户表：客户的借记卡、II类电子账户和信用卡账户';

CREATE TABLE fact_aum_monthly (
  snapshot_month DATE NOT NULL COMMENT '快照日期，为当月最后一天',
  customer_id BIGINT NOT NULL COMMENT '客户号',
  demand_deposit DECIMAL(18,2) COMMENT '活期存款余额（元）',
  time_deposit DECIMAL(18,2) COMMENT '定期存款余额（元），含大额存单',
  wealth_balance DECIMAL(18,2) COMMENT '理财产品余额（元）',
  fund_balance DECIMAL(18,2) COMMENT '公募基金市值（元）',
  insurance_value DECIMAL(18,2) COMMENT '代销保险现金价值（元）',
  total_aum DECIMAL(18,2) COMMENT 'AUM 管理资产合计（元）',
  loan_balance DECIMAL(18,2) COMMENT '个人贷款余额（元），不计入AUM',
  CONSTRAINT pk_fact_aum_monthly PRIMARY KEY (snapshot_month, customer_id)
) COMMENT '客户月末资产快照：每个客户每月末一行。AUM（管理资产）= 活期 + 定期（含大额存单）+ 理财 + 基金 + 保险现金价值，不含贷款';

CREATE TABLE fact_holding (
  holding_id BIGINT NOT NULL COMMENT '持仓ID，主键',
  customer_id BIGINT COMMENT '客户号',
  product_id BIGINT COMMENT '产品ID',
  buy_date DATE COMMENT '购买（起息）日期',
  maturity_date DATE COMMENT '到期日期，无固定期限产品为空',
  holding_amount DECIMAL(18,2) COMMENT '持有金额（元）',
  holding_status STRING COMMENT '持仓状态：持有中 / 已到期 / 已赎回',
  CONSTRAINT pk_fact_holding PRIMARY KEY (holding_id)
) COMMENT '客户持仓表：客户持有或曾经持有的定期、大额存单、理财、基金和保险';

CREATE TABLE fact_transaction (
  txn_id BIGINT NOT NULL COMMENT '交易流水号，主键',
  account_id BIGINT COMMENT '账户号',
  customer_id BIGINT COMMENT '客户号',
  txn_time TIMESTAMP COMMENT '交易时间',
  txn_type STRING COMMENT '交易类型：消费 / 转入 / 转出至本行 / 转出至他行 / 代发工资入账 / 理财申购 / 理财赎回 / 基金申购 / 取现 / 还款',
  direction STRING COMMENT '资金方向：收入 / 支出',
  channel STRING COMMENT '交易渠道：手机银行 / 网上银行 / 柜面 / ATM / POS / 第三方支付 / 批量代发',
  amount DECIMAL(18,2) COMMENT '交易金额（元）',
  counterparty STRING COMMENT '交易对手类型或消费商户类别，如 他行、本行、餐饮、商超',
  CONSTRAINT pk_fact_transaction PRIMARY KEY (txn_id)
) COMMENT '交易流水表：最近12个月客户借记卡的资金交易';

CREATE TABLE mkt_campaign (
  campaign_id BIGINT NOT NULL COMMENT '营销活动ID，主键',
  campaign_name STRING COMMENT '活动名称',
  campaign_type STRING COMMENT '活动类型：存款揽储 / 理财销售 / 基金定投 / 保险销售 / 信用卡获客 / 贷款营销 / 客户促活 / 流失挽回 / 到期承接 / 客户关怀',
  target_product_type STRING COMMENT '主推产品大类',
  start_date DATE COMMENT '活动开始日期',
  end_date DATE COMMENT '活动结束日期',
  main_channel STRING COMMENT '主要触达渠道：客户经理面访 / 外呼 / 微信 / APP推送 / 短信',
  target_rule STRING COMMENT '目标客群筛选规则',
  budget DECIMAL(18,2) COMMENT '活动预算（元）',
  owner_branch_id BIGINT COMMENT '牵头分行ID，总行统一组织的活动为空',
  campaign_status STRING COMMENT '活动状态：已结束 / 进行中 / 未开始',
  CONSTRAINT pk_mkt_campaign PRIMARY KEY (campaign_id)
) COMMENT '营销活动表：零售营销活动，如揽储、理财销售、基金定投、信用卡获客、流失挽回和到期承接';

CREATE TABLE mkt_campaign_target (
  target_id BIGINT NOT NULL COMMENT '名单记录ID，主键',
  campaign_id BIGINT COMMENT '营销活动ID',
  customer_id BIGINT COMMENT '客户号',
  rm_id BIGINT COMMENT '跟进客户经理ID，非人工渠道为空',
  assign_date DATE COMMENT '入单（下发）日期',
  contact_channel STRING COMMENT '触达渠道',
  contact_time TIMESTAMP COMMENT '触达时间，未触达为空',
  contact_result STRING COMMENT '触达结果：未触达 / 已触达未响应 / 有意向 / 明确拒绝 / 已成交',
  CONSTRAINT pk_mkt_campaign_target PRIMARY KEY (target_id)
) COMMENT '营销名单与触达记录：每行一个被纳入活动名单的客户及其触达结果';

CREATE TABLE mkt_conversion (
  conversion_id BIGINT NOT NULL COMMENT '成交记录ID，主键',
  target_id BIGINT COMMENT '对应的名单记录ID',
  campaign_id BIGINT COMMENT '营销活动ID',
  customer_id BIGINT COMMENT '客户号',
  product_id BIGINT COMMENT '成交产品ID',
  convert_date DATE COMMENT '成交日期',
  convert_amount DECIMAL(18,2) COMMENT '成交金额（元），信用卡为0',
  fee_income DECIMAL(18,2) COMMENT '中间业务收入（元），如理财、基金、保险的销售手续费',
  rm_id BIGINT COMMENT '业绩归属客户经理ID',
  CONSTRAINT pk_mkt_conversion PRIMARY KEY (conversion_id)
) COMMENT '营销成交表：营销名单中成交的业务，记录成交产品、金额和中间业务收入';

CREATE TABLE fact_customer_event (
  event_id BIGINT NOT NULL COMMENT '事件ID，主键',
  customer_id BIGINT COMMENT '客户号',
  event_type STRING COMMENT '事件类型：定期到期 / 理财到期 / 大额资金转出 / 资产下滑 / 代发停发 / 客户生日',
  event_date DATE COMMENT '事件日期（到期类为到期日）',
  related_amount DECIMAL(18,2) COMMENT '涉及金额（元）',
  detail STRING COMMENT '事件说明',
  handle_status STRING COMMENT '跟进状态：待跟进 / 已跟进',
  CONSTRAINT pk_fact_customer_event PRIMARY KEY (event_id)
) COMMENT '客户事件表（营销商机）：到期、大额资金转出、资产下滑、代发停发、生日等需要客户经理跟进的事件';

CREATE TABLE fact_customer_tag (
  customer_id BIGINT NOT NULL COMMENT '客户号',
  tag_code STRING NOT NULL COMMENT '标签编码',
  tag_name STRING COMMENT '标签名称',
  score DECIMAL(6,2) COMMENT '标签强度得分，0-100',
  tag_date DATE COMMENT '打标日期',
  CONSTRAINT pk_fact_customer_tag PRIMARY KEY (customer_id, tag_code)
) COMMENT '客户标签表：每行一个客户命中的一个营销标签';

ALTER TABLE dim_branch ADD CONSTRAINT fk_dim_branch_parent_branch_id FOREIGN KEY (parent_branch_id) REFERENCES dim_branch(branch_id);

ALTER TABLE dim_relationship_manager ADD CONSTRAINT fk_dim_relationship_manager_branch_id FOREIGN KEY (branch_id) REFERENCES dim_branch(branch_id);

ALTER TABLE dim_customer ADD CONSTRAINT fk_dim_customer_branch_id FOREIGN KEY (branch_id) REFERENCES dim_branch(branch_id);

ALTER TABLE dim_customer ADD CONSTRAINT fk_dim_customer_rm_id FOREIGN KEY (rm_id) REFERENCES dim_relationship_manager(rm_id);

ALTER TABLE fact_account ADD CONSTRAINT fk_fact_account_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE fact_account ADD CONSTRAINT fk_fact_account_branch_id FOREIGN KEY (branch_id) REFERENCES dim_branch(branch_id);

ALTER TABLE fact_aum_monthly ADD CONSTRAINT fk_fact_aum_monthly_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE fact_holding ADD CONSTRAINT fk_fact_holding_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE fact_holding ADD CONSTRAINT fk_fact_holding_product_id FOREIGN KEY (product_id) REFERENCES dim_product(product_id);

ALTER TABLE fact_transaction ADD CONSTRAINT fk_fact_transaction_account_id FOREIGN KEY (account_id) REFERENCES fact_account(account_id);

ALTER TABLE fact_transaction ADD CONSTRAINT fk_fact_transaction_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE mkt_campaign ADD CONSTRAINT fk_mkt_campaign_owner_branch_id FOREIGN KEY (owner_branch_id) REFERENCES dim_branch(branch_id);

ALTER TABLE mkt_campaign_target ADD CONSTRAINT fk_mkt_campaign_target_campaign_id FOREIGN KEY (campaign_id) REFERENCES mkt_campaign(campaign_id);

ALTER TABLE mkt_campaign_target ADD CONSTRAINT fk_mkt_campaign_target_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE mkt_campaign_target ADD CONSTRAINT fk_mkt_campaign_target_rm_id FOREIGN KEY (rm_id) REFERENCES dim_relationship_manager(rm_id);

ALTER TABLE mkt_conversion ADD CONSTRAINT fk_mkt_conversion_target_id FOREIGN KEY (target_id) REFERENCES mkt_campaign_target(target_id);

ALTER TABLE mkt_conversion ADD CONSTRAINT fk_mkt_conversion_campaign_id FOREIGN KEY (campaign_id) REFERENCES mkt_campaign(campaign_id);

ALTER TABLE mkt_conversion ADD CONSTRAINT fk_mkt_conversion_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE mkt_conversion ADD CONSTRAINT fk_mkt_conversion_product_id FOREIGN KEY (product_id) REFERENCES dim_product(product_id);

ALTER TABLE mkt_conversion ADD CONSTRAINT fk_mkt_conversion_rm_id FOREIGN KEY (rm_id) REFERENCES dim_relationship_manager(rm_id);

ALTER TABLE fact_customer_event ADD CONSTRAINT fk_fact_customer_event_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE fact_customer_tag ADD CONSTRAINT fk_fact_customer_tag_customer_id FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id);

ALTER TABLE fact_customer_tag ADD CONSTRAINT fk_fact_customer_tag_tag_code FOREIGN KEY (tag_code) REFERENCES dim_customer_tag_def(tag_code);

