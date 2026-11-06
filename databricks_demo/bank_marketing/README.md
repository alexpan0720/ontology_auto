# 零售银行客户营销演示场景

一家城商行零售条线 24 个月的客户、资产、交易与营销数据，以及在 alexpan 本体平台上配好的整套语义层、业务对象、问答、权限和订阅，用于生产级演示。

数据截至 **2026-11-05**：资产快照最新月末为 2026-10-31，交易流水覆盖 2025-11 至 2026-10。数据是确定性生成的，重复生成结果一致。

## 数据（Databricks `workspace.bank_marketing`，14 张表）

| 表 | 行数 | 说明 |
| --- | ---: | --- |
| dim_branch | 43 | 6 家分行（上海、北京、深圳、杭州、南京、成都）及下属支行 |
| dim_relationship_manager | 171 | 支行客户经理与分行私行客户经理 |
| dim_product | 52 | 存款、大额存单、理财、基金、保险、贵金属、信用卡、个人贷款 |
| dim_customer | 20,000 | 客户等级、风险测评、代发标识、管户客户经理、营销授权 |
| dim_customer_tag_def / fact_customer_tag | 12 / 约 3.9 万 | 营销标签定义与命中 |
| fact_account | 约 3.2 万 | 借记卡、II 类户、信用卡 |
| fact_aum_monthly | 约 44 万 | 每客户每月末资产快照（AUM 拆分到存款、理财、基金、保险） |
| fact_holding | 约 5.3 万 | 持仓，含到期日 |
| fact_transaction | 约 47 万 | 最近 12 个月交易流水 |
| mkt_campaign / mkt_campaign_target / mkt_conversion | 30 / 约 6.7 万 / 约 3.2 千 | 营销活动、名单触达、成交与中收 |
| fact_customer_event | 约 9 千 | 营销商机：到期、大额转出、资产下滑、代发停发、生日 |

所有表和字段都有业务口径的中文注释，声明了主键和 23 个外键。

埋入的、演示时“问得出来”的业务规律：

- **资产集中**：私行客户约占 0.5%，持有约 41% 的 AUM；钻石客户约 1%，持有约 17%。
- **流失通道**：约 6% 客户近 6 个月 AUM 持续下滑，伴随大额转出到他行，部分代发工资停发。
- **渠道差异**：成交率 客户经理面访约 25% ＞ 外呼约 6.6% ＞ 微信约 3% ＞ APP 推送约 2% ＞ 短信约 1%。
- **季节性**：季末冲存款、春节前揽储带来存款高峰。
- **到期商机**：一批定期、大额存单和理财在未来 30 天内集中到期。
- **合规问题**：少量客户持有超过自身风险测评等级的产品。

## 平台上已配置的内容

| 模块 | 内容 |
| --- | --- |
| 数据连接 | Databricks `workspace`，只采集 `bank_marketing`；已关闭“以登录用户身份认证”，所有账号用连接凭证查询 |
| 语义层 | 14 张表的语义编译、22 条语义外键 |
| 业务术语 | 14 个，中文名称并已认证（AUM 管理资产、零售客户、营销活动、营销名单、营销成交、营销商机……） |
| 业务词汇 | 文档《零售客户营销业务术语与指标口径》导入的 43 条口径 + 12 个缩写 |
| 业务背景 | 5 条：数据截止日、分行归属方法、资产口径、营销口径、合规要求 |
| 指标 | 月末 AUM、财富类资产、营销成交率、触达率、中收 |
| 认证问答 | 18 条（见 verified_queries.json），首页和问数页会把它们作为推荐问题 |
| 已保存查询 | 8 条 |
| 业务对象 | 12 个对象、20 条关系（客户 → 管户客户经理、客户 → 持仓、营销活动 → 营销名单 ……） |
| 数据域 | 客户域、资产与交易域、营销域、机构与人员域 |
| 标签 | 核心指标、营销、客户主数据、监管合规 |
| 用户组与数据权限 | 总行零售管理部（全行、明文）、上海分行零售团队 / 北京分行零售团队（只看本分行，手机号和身份证号脱敏） |
| 订阅与预警 | 4 个（资金外流预警、营销效果周报、到期资金日报、AUM 趋势），已停用，配置钉钉或飞书群机器人后启用 |

## 推荐演示路线（约 15 分钟）

1. **首页**：推荐问题、管理待办，说明“业务人员一进来就知道能问什么”。
2. **问数**：依次问——
   - 截至10月末，全行零售AUM是多少？各客户等级的AUM占比如何？（资产集中）
   - 哪个触达渠道的营销转化率最高？（渠道差异）
   - 近三个月AUM下降超过30%的客户有多少？主要集中在哪些分行？（流失预警）
   - 那上海分行呢？（多轮追问）
   - 未来30天有多少理财和定期要到期？按分行看（到期商机）
   - 有没有客户买了超过自己风险等级的产品？（合规）
   每个回答展开“数据来源”，展示用到的表、字段、术语和 SQL。
3. **业务对象**：打开一个私行客户的 360 页 → 管户客户经理、持仓、营销记录、营销商机，一页看全。
4. **数据权限**：用“上海分行零售团队”成员登录，同样的问题只返回上海分行客户，手机号脱敏；被拦截时可一键申请权限。
5. **管理中心**：接入向导、业务术语与指标口径、认证问答库、问数质量看板、订阅与预警。

## 复现

在 `auto-ontology` 目录下（需要能访问平台的 Postgres 和后端 3001 端口）：

```bash
uv run python ../databricks_demo/bank_marketing/generate.py
uv run python ../databricks_demo/bank_marketing/validate_local.py --checks
uv run --env-file .env python ../databricks_demo/bank_marketing/load_databricks.py
uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py source --keep-sso
uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py content
uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py check
uv run --env-file .env python ../databricks_demo/bank_marketing/ask.py
```

- `validate_local.py` 在本地 DuckDB 里检查分布并跑通全部认证问答 SQL，不需要 Databricks。
- `source` 阶段会触发语义编译，等它完成（管理中心 → 语义编译）再运行 `content`。
- 每一步都可重复运行，已存在的内容按名称跳过。
- `schema.sql` 是建表语句，也可以直接在 Databricks SQL Editor 里执行。
