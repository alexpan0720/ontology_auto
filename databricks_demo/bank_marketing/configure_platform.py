"""把银行客户营销演示场景配置到 alexpan 本体平台。

分三个阶段，按顺序运行（在 auto-ontology 目录下）：

    uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py source
        把 Databricks 连接的 schema 从 demo_shop 换成 bank_marketing，清掉 demo_shop
        留下的认证问答、已保存查询、订阅、权限策略和业务对象，然后重建语义层。
        语义编译要调用大模型，需要十几分钟到半小时。

    uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py content
        等语义编译完成后运行：语义输入（缩写与业务背景）、术语文档导入、认证问答、
        已保存查询、业务对象、数据域、标签、用户组与数据权限、指标订阅、指标（SQL 属性）。

    uv run --env-file .env python ../databricks_demo/bank_marketing/configure_platform.py check
        打印配置结果汇总。

每一步都可重复运行：已存在的内容按名称跳过，不会重复创建。
通过后端 API（默认 http://localhost:3001，带管理员身份）写入，与在界面上操作效果相同；
语义输入存在前端库里，直接写 frontend schema。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
API = "http://localhost:3001/api"
DATABASE = "workspace"
SCHEMA = "bank_marketing"
OLD_SCHEMA = "demo_shop"


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def admin_id() -> str:
    from auto_ontology.dal.session import store

    rows = store().query_read("SELECT id FROM frontend.\"user\" WHERE role = 'admin' ORDER BY \"createdAt\" LIMIT 1")
    if not rows:
        raise SystemExit("找不到管理员账号")
    return rows[0]["id"]


ADMIN = ""


def call(method: str, path: str, body: Any = None, *, ok_missing: bool = False) -> Any:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8", "x-auto-ontology-user-id": ADMIN},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        if ok_missing and exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def upload(path: str, file: Path) -> Any:
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file.name}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "x-auto-ontology-user-id": ADMIN},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def step(title: str) -> None:
    print(f"\n== {title}")


def tables() -> dict[str, dict]:
    """bank_marketing tables in the platform catalog, by name."""
    from auto_ontology.dal import objects as objects_dal

    return {
        t["name"]: t
        for t in objects_dal.fetch_catalog_tables()
        if t["database_name"] == DATABASE and t["schema_name"] == SCHEMA
    }


# ---------------------------------------------------------------------------
# Phase 1: switch the source
# ---------------------------------------------------------------------------


def phase_source(disable_sso: bool) -> None:
    step("切换数据源到 bank_marketing")
    connections = call("GET", "/connections")["data"]
    current = next(c for c in connections if c["database_name"] == DATABASE)["connection"]
    if current.get("schemas") != [SCHEMA]:
        call("PUT", f"/connections/{DATABASE}", {"connection": {**current, "schemas": [SCHEMA]}})
        print("连接的 schema 已改为 bank_marketing（会自动重新采集元数据）")
    else:
        print("连接已指向 bank_marketing")
    if disable_sso and current.get("sso_federation"):
        call("PATCH", f"/connections/{DATABASE}/sso-federation", {"enabled": False})
        print("已关闭“以登录用户身份认证”，演示账号用邮箱密码登录即可问数")

    step("清理 demo_shop 留下的内容")
    for item in call("GET", "/verified-queries")["data"]:
        if OLD_SCHEMA in item["sql"]:
            call("DELETE", f"/verified-queries/{item['id']}")
            print(f"删除认证问答：{item['question']}")
    for item in call("GET", "/custom-analyses?limit=100").get("data", []):
        if OLD_SCHEMA in (item.get("sql") or ""):
            call("DELETE", f"/custom-analyses/{item['id']}")
            print(f"删除已保存查询：{item['name']}")
    for item in call("GET", "/subscriptions")["data"]:
        if OLD_SCHEMA in item["sql"]:
            call("DELETE", f"/subscriptions/{item['id']}")
            print(f"删除订阅：{item['name']}")
    for item in call("GET", "/access-policies")["data"]:
        if item.get("schema_name") == OLD_SCHEMA:
            call("DELETE", f"/access-policies/{item['id']}")
            print(f"删除权限策略：{item.get('table_name')}.{item.get('column_name') or item.get('predicate')}")
    old_types = [t for t in call("GET", "/object-types")["data"] if t["schema_name"] == OLD_SCHEMA]
    if old_types:
        call("POST", "/object-types/bulk", {"ids": [t["id"] for t in old_types], "action": "delete"})
        print(f"删除业务对象 {len(old_types)} 个")

    step("等待元数据采集")
    for _ in range(60):
        if len(tables()) >= 14:
            break
        time.sleep(10)
    print(f"已采集 bank_marketing 表：{len(tables())} 张")

    step("重建语义层")
    call("POST", "/semantic-compilation/reset")
    print("已触发语义层重建。完成后运行 content 阶段；进度见「管理中心 → 语义编译」。")


# ---------------------------------------------------------------------------
# Phase 2: content
# ---------------------------------------------------------------------------

CUSTOM_ANALYSES = [
    ("月末AUM按客户等级分布", "最新月末各客户等级的客户数、AUM及占比", 0),
    ("分行AUM较年初增长", "各分行10月末AUM与年初对比", 2),
    ("资金外流风险客户清单", "近三个月AUM下降超过30%的客户，流失挽回名单", 4),
    ("未来30天到期资金", "按分行和产品大类汇总未来30天到期金额，到期承接商机", 5),
    ("营销活动效果看板", "2026年各营销活动的触达、成交与中收", 6),
    ("渠道转化率对比", "各触达渠道的触达率与成交率", 7),
    ("客户经理营销业绩", "2026年客户经理营销成交金额排名", 8),
    ("超风险持仓排查", "产品风险等级高于客户测评等级的持仓，适当性合规", 11),
]

ZONES = [
    ("客户域", "客户基本信息、标签与营销商机", "#2563eb", ["dim_customer", "dim_customer_tag_def", "fact_customer_tag", "fact_customer_event"]),
    ("资产与交易域", "账户、月末资产、持仓、产品与交易流水", "#059669", ["fact_account", "fact_aum_monthly", "fact_holding", "fact_transaction", "dim_product"]),
    ("营销域", "营销活动、名单触达与成交", "#d97706", ["mkt_campaign", "mkt_campaign_target", "mkt_conversion"]),
    ("机构与人员域", "分支机构与客户经理", "#7c3aed", ["dim_branch", "dim_relationship_manager"]),
]

TABLE_TAGS = {
    "核心指标": ["fact_aum_monthly", "mkt_conversion"],
    "营销": ["mkt_campaign", "mkt_campaign_target", "mkt_conversion", "fact_customer_event", "fact_customer_tag"],
    "客户主数据": ["dim_customer"],
    "监管合规": ["fact_holding", "dim_product"],
}

LINK_NAMES = {
    # (源表, 源字段, 目标表): (正向名称, 反向名称)
    ("dim_customer", "rm_id", "dim_relationship_manager"): ("管户客户经理", "管户客户"),
    ("dim_customer", "branch_id", "dim_branch"): ("开户机构", "开户客户"),
    ("dim_branch", "parent_branch_id", "dim_branch"): ("上级分行", "下属支行"),
    ("fact_holding", "customer_id", "dim_customer"): ("持有客户", "持仓"),
    ("fact_holding", "product_id", "dim_product"): ("产品", "持仓"),
    ("mkt_campaign_target", "campaign_id", "mkt_campaign"): ("营销活动", "营销名单"),
    ("mkt_campaign_target", "customer_id", "dim_customer"): ("客户", "营销记录"),
    ("mkt_conversion", "campaign_id", "mkt_campaign"): ("营销活动", "成交记录"),
    ("mkt_conversion", "customer_id", "dim_customer"): ("客户", "营销成交"),
    ("mkt_conversion", "rm_id", "dim_relationship_manager"): ("业绩客户经理", "营销成交"),
    ("fact_customer_event", "customer_id", "dim_customer"): ("客户", "营销商机"),
    ("fact_account", "customer_id", "dim_customer"): ("客户", "账户"),
}

TYPE_NAMES = {
    "dim_customer": ("客户", "零售个人客户，含客户等级、风险测评和管户客户经理"),
    "dim_relationship_manager": ("客户经理", "零售客户经理与私行客户经理"),
    "dim_branch": ("机构", "分行与支行"),
    "dim_product": ("金融产品", "存款、理财、基金、保险、信用卡和贷款产品"),
    "fact_account": ("账户", "借记卡、电子账户与信用卡账户"),
    "fact_holding": ("持仓", "客户持有的定期、理财、基金和保险"),
    "mkt_campaign": ("营销活动", "零售营销活动"),
    "mkt_campaign_target": ("营销名单", "活动名单与触达结果"),
    "mkt_conversion": ("营销成交", "营销带来的成交业务"),
    "fact_customer_event": ("营销商机", "到期、资金转出、资产下滑等需跟进的客户事件"),
    "fact_transaction": ("交易", "借记卡交易流水"),
    "dim_customer_tag_def": ("客户标签", "营销用客户标签定义"),
}

GROUPS = [
    ("总行零售管理部", "可查看全行客户数据，客户敏感信息不脱敏", "#0ea5e9"),
    ("上海分行零售团队", "只能查看上海分行的客户，客户敏感信息脱敏", "#14b8a6"),
    ("北京分行零售团队", "只能查看北京分行的客户，客户敏感信息脱敏", "#f97316"),
]

#: Business terms come out of compilation named in English, one per table;
#: the demo shows them under Chinese names, and certified.
TERM_NAMES = {
    "Assets Under Management": ("AUM 管理资产", "客户在本行的金融资产合计（活期+定期含大额存单+理财+基金+保险现金价值，不含贷款），按月末快照统计，取 fact_aum_monthly。"),
    "Customer": ("零售客户", "本行零售个人客户，含客户等级、风险测评、代发标识和管户客户经理。"),
    "Account": ("账户", "客户的 I 类借记卡、II 类电子账户和信用卡账户。"),
    "Branch": ("经营机构", "分行与支行，支行通过上级机构归属到分行。"),
    "Campaign Target": ("营销名单", "被纳入营销活动、需要触达的客户及其触达结果；用于计算触达率和成交率。"),
    "Conversion": ("营销成交", "营销名单中成交的业务，含成交产品、成交金额和中间业务收入。"),
    "Customer Event": ("营销商机", "需要客户经理跟进的客户事件：到期、大额资金转出、资产下滑、代发停发、生日。"),
    "Customer Tag": ("客户标签", "客户命中的营销标签及强度得分。"),
    "Customer Tag Definition": ("标签定义", "营销用客户标签的编码、名称和打标规则。"),
    "Holding": ("客户持仓", "客户持有或曾持有的定期、大额存单、理财、基金和保险。"),
    "Marketing Campaign": ("营销活动", "零售营销活动，包括揽储、理财销售、基金定投、保险、信用卡获客、贷款营销、促活、流失挽回、到期承接。"),
    "Product": ("金融产品", "零售产品目录，含产品大类、风险等级、期限和收益。"),
    "Relationship Manager": ("客户经理", "零售客户经理与私行客户经理。"),
    "Transaction": ("交易流水", "最近 12 个月借记卡资金交易，含代发工资、转入转出、消费、申赎等。"),
}

METRICS = [
    # (术语名称候选, 指标名称, 说明, SQL)
    (["AUM 管理资产"], "月末AUM合计", "最新月末全行零售AUM（元）",
     f"SELECT sum(total_aum) AS total_aum FROM {DATABASE}.{SCHEMA}.fact_aum_monthly WHERE snapshot_month = (SELECT max(snapshot_month) FROM {DATABASE}.{SCHEMA}.fact_aum_monthly)"),
    (["AUM 管理资产"], "月末财富类资产", "理财+基金+保险现金价值合计（元）",
     f"SELECT sum(wealth_balance + fund_balance + insurance_value) AS wealth_aum FROM {DATABASE}.{SCHEMA}.fact_aum_monthly WHERE snapshot_month = (SELECT max(snapshot_month) FROM {DATABASE}.{SCHEMA}.fact_aum_monthly)"),
    (["营销名单"], "营销成交率", "已成交名单数/名单总数",
     f"SELECT avg(CASE WHEN contact_result = '已成交' THEN 1 ELSE 0 END) AS conversion_rate FROM {DATABASE}.{SCHEMA}.mkt_campaign_target"),
    (["营销名单"], "营销触达率", "已触达名单数/名单总数",
     f"SELECT avg(CASE WHEN contact_result <> '未触达' THEN 1 ELSE 0 END) AS reach_rate FROM {DATABASE}.{SCHEMA}.mkt_campaign_target"),
    (["营销成交"], "营销中收合计", "营销成交带来的中间业务收入（元）",
     f"SELECT sum(fee_income) AS fee_income FROM {DATABASE}.{SCHEMA}.mkt_conversion"),
]

#: The scheduler's weekday numbering (see auto_ontology/subscriptions/schedule.py).
WEEKDAY_MONDAY = 1

SUBSCRIPTIONS = [
    # (名称, 认证问答序号, 频率, 时间, 预警)
    ("每日·资金外流风险客户", 4, "workdays", "08:30", dict(alert_type="threshold", alert_column="下降幅度_pct", alert_op=">", alert_value=60, push_mode="on_alert")),
    ("每周一·营销活动效果", 6, "weekly", "09:00", dict(weekday=WEEKDAY_MONDAY)),
    ("每日·未来30天到期资金", 5, "workdays", "08:45", dict()),
    ("每月·全行AUM趋势", 1, "daily", "09:00", dict(alert_type="change", alert_column="AUM_亿元", alert_op="down", alert_value=3, push_mode="on_alert")),
]


def phase_content() -> None:
    from auto_ontology.dal.session import store

    by_name = tables()
    if len(by_name) < 14:
        raise SystemExit(f"bank_marketing 只采集到 {len(by_name)} 张表，先运行 source 阶段并等待采集完成")
    status = call("GET", "/semantic-compilation/status")
    if status.get("running"):
        print("提示：语义编译仍在运行，术语和业务对象会在编译完成后更完整。")

    step("语义输入：缩写与业务背景")
    semantic = json.loads((HERE / "semantic_input.json").read_text(encoding="utf-8"))
    for item in semantic["acronyms"]:
        store().query_write(
            "INSERT INTO frontend.acronyms (id, name, description, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :name, :description, now(), now()) "
            "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, updated_at = now()",
            {"name": item["name"], "description": item["description"]},
        )
    existing = {r["content"] for r in store().query_read("SELECT content FROM frontend.prompts")}
    for content in semantic["prompts"]:
        if content not in existing:
            store().query_write(
                "INSERT INTO frontend.prompts (id, content) VALUES (gen_random_uuid(), :content)",
                {"content": content},
            )
    print(f"缩写 {len(semantic['acronyms'])} 条，业务背景 {len(semantic['prompts'])} 条")

    step("术语文档导入")
    doc = HERE / "零售客户营销业务术语与指标口径.md"
    batches = call("GET", "/glossary-imports")["data"]
    batch = next((b for b in batches if b["file_name"] == doc.name), None)
    if batch is None:
        batch = {"id": upload("/glossary-imports", doc)["id"]}
        print("已上传，等待大模型抽取术语…")
    for _ in range(90):
        detail = call("GET", f"/glossary-imports/{batch['id']}")
        if detail["status"] in ("done", "failed"):
            break
        time.sleep(10)
    if detail["status"] == "failed":
        print(f"术语抽取失败：{detail.get('error_message')}")
    else:
        pending = [c["id"] for c in detail["candidates"] if c["status"] == "pending"]
        if pending:
            result = call("POST", f"/glossary-imports/{batch['id']}/apply", {"candidate_ids": pending, "overwrite_existing": True, "update_terms": True})
            print(f"已应用候选术语：{result}")
        else:
            print("候选术语已全部处理")

    step("认证问答")
    questions = json.loads((HERE / "verified_queries.json").read_text(encoding="utf-8"))
    existing_q = {v["question"]: v for v in call("GET", "/verified-queries")["data"]}
    certified_ids: list[str | None] = []
    for item in questions:
        found = existing_q.get(item["question"])
        if found:
            certified_ids.append(found["id"])
            continue
        res = call("POST", "/verified-queries", {"question": item["question"], "sql": item["sql"], "database_name": DATABASE, "note": item.get("note"), "status": "certified"})
        certified_ids.append(res["id"])
    print(f"认证问答 {len(questions)} 条")

    step("已保存查询")
    saved = {a["name"] for a in call("GET", "/custom-analyses?limit=100").get("data", [])}
    for name, description, index in CUSTOM_ANALYSES:
        if name in saved:
            continue
        try:
            call("POST", "/custom-analyses", {"name": name, "description": description, "sql": questions[index]["sql"]})
        except RuntimeError as exc:
            print(f"跳过 {name}：{exc}")
    print(f"已保存查询 {len(CUSTOM_ANALYSES)} 条")

    step("业务对象")
    gen = call("POST", "/object-types/generate")
    print(f"新增候选对象 {gen['types']} 个、关系 {gen['links']} 个")
    types = [t for t in call("GET", "/object-types")["data"] if t["schema_name"] == SCHEMA]
    call("POST", "/object-types/bulk", {"ids": [t["id"] for t in types], "action": "accept"})
    by_table = {t["table_name"]: t for t in types}
    for table_name, (display, description) in TYPE_NAMES.items():
        if table_name in by_table:
            call("PATCH", f"/object-types/{by_table[table_name]['id']}", {"display_name": display, "description": description})
    # 资产快照、标签明细是按月或按客户的明细，不适合作为独立业务对象
    for table_name in ("fact_aum_monthly", "fact_customer_tag"):
        if table_name in by_table:
            call("DELETE", f"/object-types/{by_table[table_name]['id']}", ok_missing=True)
    renamed = 0
    for t in types:
        detail = call("GET", f"/object-types/{t['id']}", ok_missing=True)
        if not detail:
            continue
        for link in detail["links"]:
            if link["object_type_id"] != t["id"]:
                continue
            key = (t["table_name"], link["source_column"], link["target_type"]["table_name"] if link["target_type"] else None)
            if key in LINK_NAMES:
                forward, reverse = LINK_NAMES[key]
                call("PATCH", f"/link-types/{link['id']}", {"display_name": forward, "reverse_display_name": reverse, "status": "active"})
                renamed += 1
    print(f"业务对象 {len(TYPE_NAMES)} 个，已命名关系 {renamed} 条")

    step("数据域")
    zones = {z["name"] for z in call("GET", f"/zones?uid={ADMIN}").get("data", [])}
    for name, description, color, table_names in ZONES:
        if name in zones:
            continue
        call("POST", "/zones", {"name": name, "description": description, "color": color, "items": [by_name[t]["id"] for t in table_names], "created_by": ADMIN})
    print(f"数据域 {len(ZONES)} 个")

    step("标签")
    tag_ids = {t["name"]: t["id"] for t in call("GET", "/tags?limit=100").get("data", [])}
    for tag, table_names in TABLE_TAGS.items():
        tag_id = tag_ids.get(tag) or call("POST", "/tags", {"name": tag})["data"]["id"]
        for t in table_names:
            call("POST", f"/tags/{tag_id}/targets", {"type": "table", "id": by_name[t]["id"]})
    print(f"标签 {len(TABLE_TAGS)} 个")

    step("用户组与数据权限")
    groups = {g["name"]: g["id"] for g in call("GET", "/groups")["data"]}
    for name, description, color in GROUPS:
        if name not in groups:
            groups[name] = call("POST", "/groups", {"name": name, "description": description, "color": color, "role": "viewer"})["data"]["id"]
    customer = by_name["dim_customer"]["id"]
    policies = call("GET", "/access-policies")["data"]
    have = {(p["kind"], p.get("column_name"), p.get("predicate")) for p in policies if p.get("schema_name") == SCHEMA}
    wanted = [
        dict(kind="mask", table_id=customer, column_name="mobile", mask_style="phone", group_ids=[groups["总行零售管理部"]], description="客户手机号脱敏，总行零售管理部可见明文"),
        dict(kind="mask", table_id=customer, column_name="id_card_no", mask_style="id_number", group_ids=[groups["总行零售管理部"]], description="身份证号脱敏，总行零售管理部可见明文"),
        dict(kind="row", table_id=customer, predicate="1 = 1", group_ids=[groups["总行零售管理部"]], description="总行可查看全行客户"),
        dict(kind="row", table_id=customer, predicate="branch_id BETWEEN 100 AND 199", group_ids=[groups["上海分行零售团队"]], description="上海分行只能查看本分行客户"),
        dict(kind="row", table_id=customer, predicate="branch_id BETWEEN 200 AND 299", group_ids=[groups["北京分行零售团队"]], description="北京分行只能查看本分行客户"),
    ]
    for policy in wanted:
        if (policy["kind"], policy.get("column_name"), policy.get("predicate")) in have:
            continue
        call("POST", "/access-policies", policy)
    print(f"用户组 {len(GROUPS)} 个，权限策略 {len(wanted)} 条")

    step("指标订阅（已建好，配置推送渠道后启用）")
    subs = {s["name"] for s in call("GET", "/subscriptions")["data"]}
    for name, index, schedule, at, alert in SUBSCRIPTIONS:
        if name in subs:
            continue
        call("POST", "/subscriptions", {"name": name, "sql": questions[index]["sql"], "database_name": DATABASE, "verified_query_id": certified_ids[index], "schedule": schedule, "time_of_day": at, "enabled": False, **alert})
    print(f"订阅 {len(SUBSCRIPTIONS)} 个")

    step("业务术语：中文名称并认证")
    for term in call("GET", "/terms")["terms"]:
        if term["name"] in TERM_NAMES:
            name, description = TERM_NAMES[term["name"]]
            # A description the glossary import already wrote in Chinese is kept.
            keep = any("一" <= ch <= "鿿" for ch in term.get("description") or "")
            call("PATCH", f"/terms/{term['id']}", {"name": name, "description": term["description"] if keep else description, "name_certified": True, "description_certified": True})
    print(f"术语 {len(TERM_NAMES)} 个已改为中文并认证")

    step("指标（SQL 属性）")
    terms = {t["name"]: t["id"] for t in call("GET", "/terms")["terms"]}
    made = 0
    for candidates, name, description, sql in METRICS:
        term_id = next((terms[c] for c in candidates if c in terms), None)
        if term_id is None:
            # Glossary import may word a term a little differently; take the
            # closest name that contains the first candidate.
            term_id = next((tid for tname, tid in terms.items() if candidates[-1] in tname), None)
        if term_id is None:
            print(f"跳过 {name}：没找到术语 {candidates[0]}")
            continue
        try:
            call("POST", "/sql-attributes", {"name": name, "description": description, "expression": sql, "term_id": term_id})
            made += 1
        except RuntimeError as exc:
            if "409" not in str(exc):
                print(f"跳过 {name}：{exc}")
    print(f"指标 {made} 个")


# ---------------------------------------------------------------------------
# Phase 3: summary
# ---------------------------------------------------------------------------


def phase_check() -> None:
    by_name = tables()
    rows = {
        "已采集的表": len(by_name),
        "语义编译": call("GET", "/semantic-compilation/status"),
        "术语": call("GET", "/terms?limit=1").get("total"),
        "认证问答": call("GET", "/verified-queries")["count"],
        "已保存查询": call("GET", "/custom-analyses?limit=1").get("total"),
        "业务对象": call("GET", "/object-types")["summary"],
        "数据域": len(call("GET", f"/zones?uid={ADMIN}").get("data", [])),
        "用户组": call("GET", "/groups")["count"],
        "权限策略": call("GET", "/access-policies")["count"],
        "订阅": call("GET", "/subscriptions")["count"],
    }
    for key, value in rows.items():
        print(f"{key:8s} {value}")


def main() -> None:
    global ADMIN
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=["source", "content", "check"])
    parser.add_argument("--keep-sso", action="store_true", help="保留“以登录用户身份认证”（默认关闭，便于用邮箱密码账号演示）")
    args = parser.parse_args()
    ADMIN = admin_id()
    if args.phase == "source":
        phase_source(disable_sso=not args.keep_sso)
    elif args.phase == "content":
        phase_content()
    else:
        phase_check()


if __name__ == "__main__":
    sys.exit(main())
