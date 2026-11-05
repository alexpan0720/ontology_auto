"""零售银行客户营销演示数据生成器。

生成一家城商行零售条线 24 个月的客户、资产、交易与营销数据，写成 Parquet，
由 load_databricks.py 导入 Databricks（或由 validate_local.py 载入 DuckDB 校验）。

数据是确定性的：固定随机种子，重复运行结果一致。"今天"固定为 2026-11-05，
资产快照覆盖 2024-11 至 2026-10，交易流水覆盖最近 12 个月。

刻意埋入、供演示时"问得出来"的业务规律：
  * 资产高度集中：约 2% 的私行/钻石客户贡献过半 AUM；
  * 约 6% 客户处于流失通道：近 6 个月 AUM 持续下滑，伴随大额转出到他行；
  * 代发工资客户每月固定入账，停发即为流失信号；
  * 营销转化率因渠道差异明显：客户经理面访 > 外呼 > APP 推送 > 短信；
  * 季末（3/6/9/12 月）存款冲高，春节前揽储活动带来定期存款高峰；
  * 风险等级与产品适配：C1/C2 客户极少持有 R4/R5 产品，但仍有少量"超风险持有"留作合规问题；
  * 一批定期存款与理财将在未来 30 天内集中到期，是"到期承接"营销的商机。

用法：
    python generate.py --out ./out [--customers 20000]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261105
TODAY = date(2026, 11, 5)
MONTHS = 24  # 2024-11 .. 2026-10
TXN_START = date(2025, 11, 1)
TXN_END = date(2026, 10, 31)

rng = np.random.default_rng(SEED)


def month_ends(n: int, last: date) -> list[date]:
    """The last day of each of the *n* months ending with *last*'s month."""
    out = []
    y, m = last.year, last.month
    for _ in range(n):
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        out.append(nxt - timedelta(days=1))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


SNAPSHOTS = month_ends(MONTHS, date(2026, 10, 31))


# ---------------------------------------------------------------------------
# 机构与客户经理
# ---------------------------------------------------------------------------

BRANCHES = {
    # 分行: (城市, 区域, [支行])
    "上海分行": ("上海", "华东", ["陆家嘴支行", "徐家汇支行", "静安支行", "虹桥支行", "张江支行", "五角场支行", "闵行支行", "浦东机场支行"]),
    "北京分行": ("北京", "华北", ["国贸支行", "中关村支行", "金融街支行", "望京支行", "亦庄支行", "西单支行", "亚运村支行"]),
    "深圳分行": ("深圳", "华南", ["福田支行", "南山科技园支行", "前海支行", "罗湖支行", "宝安中心支行", "龙华支行"]),
    "杭州分行": ("杭州", "华东", ["钱江新城支行", "西湖支行", "滨江支行", "未来科技城支行", "萧山支行", "余杭支行"]),
    "南京分行": ("南京", "华东", ["新街口支行", "河西支行", "江宁支行", "鼓楼支行", "仙林支行"]),
    "成都分行": ("成都", "西南", ["天府新区支行", "春熙路支行", "高新支行", "金牛支行", "武侯支行"]),
}
#: 客户在各分行的分布：一线城市客户多、资产高。
BRANCH_WEIGHT = {"上海分行": 0.26, "北京分行": 0.22, "深圳分行": 0.18, "杭州分行": 0.14, "南京分行": 0.11, "成都分行": 0.09}
BRANCH_WEALTH = {"上海分行": 1.35, "北京分行": 1.3, "深圳分行": 1.25, "杭州分行": 1.1, "南京分行": 0.95, "成都分行": 0.8}

SURNAMES = list("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
GIVEN = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平", "刚", "桂英", "建华", "文", "华", "建国", "志强", "晓明", "雪", "婷", "宇", "浩", "鑫", "欣怡", "子涵", "梓轩", "思远", "嘉怡", "一鸣", "雨桐", "俊杰", "佳琪", "晨", "昊天", "梦瑶", "天佑", "诗涵", "博文", "海燕", "红梅", "玉兰", "国庆", "卫东", "建军", "立新", "淑珍", "凤英", "晓燕", "慧", "琳"]

AREA_CODE = {"上海": "310115", "北京": "110105", "深圳": "440304", "杭州": "330106", "南京": "320106", "成都": "510107"}


def person_name(r: np.random.Generator) -> str:
    return SURNAMES[r.integers(len(SURNAMES))] + GIVEN[r.integers(len(GIVEN))]


def id_card(area: str, birth: date, r: np.random.Generator) -> str:
    """A well-formed but fictitious 18-digit resident ID (valid check digit)."""
    body = f"{area}{birth:%Y%m%d}{r.integers(0, 1000):03d}"
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check = "10X98765432"[sum(int(c) * w for c, w in zip(body, weights)) % 11]
    return body + check


def mobile(r: np.random.Generator) -> str:
    return f"1{r.choice([3, 5, 7, 8, 9])}{r.integers(0, 10)}{r.integers(0, 10**8):08d}"


def build_branches() -> pd.DataFrame:
    rows = []
    bid = 100
    for i, (name, (city, region, subs)) in enumerate(BRANCHES.items(), start=1):
        parent = i * 100
        rows.append(dict(branch_id=parent, branch_name=name, branch_level="分行", parent_branch_id=None, city=city, region=region, open_date=date(2008 + i, 3, 1)))
        for j, sub in enumerate(subs, start=1):
            rows.append(dict(branch_id=parent + j, branch_name=f"{city}{sub}" if not sub.startswith(city) else sub, branch_level="支行", parent_branch_id=parent, city=city, region=region, open_date=date(2010 + (j % 9), 1 + j % 12, 15)))
        bid += 1
    return pd.DataFrame(rows)


def build_rms(branches: pd.DataFrame) -> pd.DataFrame:
    r = np.random.default_rng(SEED + 1)
    rows = []
    rid = 1
    for b in branches.itertuples():
        if b.branch_level == "分行":
            # 分行私行中心：资深私行客户经理
            for _ in range(3):
                rows.append(dict(rm_id=rid, rm_name=person_name(r), branch_id=b.branch_id, rm_level="私行客户经理", hire_date=date(int(r.integers(2009, 2017)), int(r.integers(1, 13)), 1), mobile=mobile(r), status="在岗"))
                rid += 1
            continue
        n = int(r.integers(3, 6))
        for k in range(n):
            level = r.choice(["初级客户经理", "中级客户经理", "高级客户经理", "资深客户经理"], p=[0.3, 0.35, 0.25, 0.1])
            hire = date(int(r.integers(2012, 2026)), int(r.integers(1, 13)), 1)
            status = "离职" if r.random() < 0.04 else "在岗"
            rows.append(dict(rm_id=rid, rm_name=person_name(r), branch_id=b.branch_id, rm_level=level, hire_date=hire, mobile=mobile(r), status=status))
            rid += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 产品
# ---------------------------------------------------------------------------

PRODUCT_SPECS = [
    # (类型, 名称模板, 风险, 期限天, 预期收益, 起购, 数量)
    ("活期存款", ["个人活期储蓄"], "R1", 0, 0.0015, 0, 1),
    ("定期存款", ["整存整取三个月", "整存整取六个月", "整存整取一年", "整存整取两年", "整存整取三年", "整存整取五年"], "R1", None, None, 50, 6),
    ("大额存单", ["个人大额存单1年期", "个人大额存单2年期", "个人大额存单3年期", "新春专享大额存单"], "R1", None, None, 200000, 4),
    ("理财产品", ["稳盈现金管理1号", "稳盈30天持有期", "稳盈90天持有期", "安鑫180天", "安鑫一年定开", "睿享固收+两年", "睿享混合偏债", "臻选权益增强", "养老理财2030", "新客专享理财"], None, None, None, 10000, 10),
    ("公募基金", ["沪深300指数增强", "中证500指数", "科技创新混合", "消费升级股票", "医疗健康混合", "稳健债券A", "短债增强C", "货币基金A", "纳斯达克100QDII", "红利低波动ETF联接", "新能源产业混合", "价值精选混合"], None, 0, None, 10, 12),
    ("保险", ["终身寿险尊享版", "年金险金福版", "重疾险守护版", "增额终身寿险", "医疗险百万版", "教育年金险"], "R2", None, None, 5000, 6),
    ("贵金属", ["积存金", "实物金条10g", "实物金条50g"], "R4", 0, None, 1000, 3),
    ("信用卡", ["标准金卡", "白金卡", "钻石卡", "联名卡·航旅", "联名卡·电商", "年轻卡"], "R1", 0, None, 0, 6),
    ("个人贷款", ["个人住房按揭贷款", "个人消费贷·信易贷", "经营贷·小微快贷", "个人汽车贷款"], "R1", None, None, 10000, 4),
]


def build_products() -> pd.DataFrame:
    r = np.random.default_rng(SEED + 2)
    rows = []
    pid = 1001
    for ptype, names, risk, term, yld, min_amt, _ in PRODUCT_SPECS:
        for name in names:
            if ptype == "定期存款":
                months = {"三个月": 3, "六个月": 6, "一年": 12, "两年": 24, "三年": 36, "五年": 60}[name.replace("整存整取", "")]
                p_term, p_yield, p_risk = months * 30, {3: 0.0115, 6: 0.0135, 12: 0.0155, 24: 0.0165, 36: 0.0195, 60: 0.0200}[months], "R1"
            elif ptype == "大额存单":
                years = 2 if "2年" in name else 3 if "3年" in name else 1
                p_term, p_yield, p_risk = years * 365, 0.0175 + 0.002 * years, "R1"
            elif ptype == "理财产品":
                if "现金" in name:
                    p_term, p_yield, p_risk = 0, 0.019, "R1"
                elif "权益" in name:
                    p_term, p_yield, p_risk = 365, 0.055, "R4"
                elif "混合" in name or "固收+" in name or "养老" in name:
                    p_term, p_yield, p_risk = 365 * (2 if "两年" in name else 1), 0.038, "R3"
                else:
                    p_term = 30 if "30" in name else 90 if "90" in name else 180 if "180" in name else 365
                    p_yield, p_risk = 0.024 + p_term / 365 * 0.006, "R2"
            elif ptype == "公募基金":
                if "货币" in name:
                    p_risk, p_yield = "R1", 0.017
                elif "债" in name:
                    p_risk, p_yield = "R2", 0.03
                elif "QDII" in name or "新能源" in name or "科技" in name:
                    p_risk, p_yield = "R5", None
                else:
                    p_risk, p_yield = "R4", None
                p_term = 0
            elif ptype == "保险":
                p_term, p_yield, p_risk = (3650 if "年金" in name or "增额" in name else 365), (0.03 if "年金" in name or "增额" in name else None), "R2"
            elif ptype == "个人贷款":
                p_term = 30 * 365 if "住房" in name else 3 * 365 if "汽车" in name else 365
                p_yield, p_risk = {"住房": 0.031, "消费": 0.0385, "经营": 0.035, "汽车": 0.042}[next(k for k in ["住房", "消费", "经营", "汽车"] if k in name)], "R1"
            else:
                p_term, p_yield, p_risk = term or 0, yld, risk or "R1"
            launch = date(2018, 1, 1) + timedelta(days=int(r.integers(0, 2700)))
            if "新春" in name:
                launch = date(2026, 1, 10)
            if "新客" in name:
                launch = date(2025, 6, 1)
            status = "停售" if r.random() < 0.06 else "在售"
            rows.append(dict(product_id=pid, product_name=name, product_type=ptype, risk_rating=p_risk, term_days=p_term, expected_yield=p_yield, min_amount=float(min_amt), launch_date=launch, status=status))
            pid += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 客户与资产
# ---------------------------------------------------------------------------

OCCUPATIONS = ["企业职员", "公务员/事业单位", "私营业主", "专业人士(医生/律师/教师)", "企业高管", "自由职业", "退休", "学生"]
INCOME_BANDS = ["10万以下", "10-30万", "30-50万", "50-100万", "100万以上"]
LEVEL_THRESHOLDS = [(6_000_000, "私行"), (2_000_000, "钻石"), (500_000, "白金"), (50_000, "金卡"), (0, "普通")]


def level_of(aum: float) -> str:
    return next(name for floor, name in LEVEL_THRESHOLDS if aum >= floor)


@dataclass
class Trajectory:
    total: np.ndarray  # per snapshot, 0 before opening
    deposit_share: float
    wealth_share: float
    fund_share: float
    insurance_share: float
    pattern: str  # 稳定 / 增长 / 流失 / 新客 / 沉睡


def build_customers(n: int, branches: pd.DataFrame, rms: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, Trajectory]]:
    r = np.random.default_rng(SEED + 3)
    sub = branches[branches.branch_level == "支行"]
    parents = list(BRANCH_WEIGHT)
    rows, trajectories = [], {}
    for cid in range(1, n + 1):
        customer_id = 10_000_000 + cid
        parent = parents[r.choice(len(parents), p=list(BRANCH_WEIGHT.values()))]
        parent_id = branches[branches.branch_name == parent].branch_id.iloc[0]
        candidates = sub[sub.parent_branch_id == parent_id]
        branch = candidates.iloc[int(r.integers(len(candidates)))]
        city = branch.city

        age = int(np.clip(r.normal(42, 14), 19, 85))
        birth = date(TODAY.year - age, int(r.integers(1, 13)), int(r.integers(1, 29)))
        gender = "男" if r.random() < 0.49 else "女"
        if age >= 60:
            occupation = "退休" if r.random() < 0.8 else r.choice(["私营业主", "企业高管"])
        elif age <= 22:
            occupation = "学生" if r.random() < 0.7 else "企业职员"
        else:
            occupation = r.choice(OCCUPATIONS[:6], p=[0.42, 0.15, 0.13, 0.12, 0.07, 0.11])

        # 潜在财富：收入 x 年龄积累 x 城市系数，长尾对数正态
        income_mult = {"企业高管": 3.2, "私营业主": 3.6, "专业人士(医生/律师/教师)": 1.8, "公务员/事业单位": 1.2, "企业职员": 1.0, "自由职业": 0.9, "退休": 1.1, "学生": 0.15}[occupation]
        wealth_z = r.normal(0, 1.25)
        base = 28_000 * income_mult * BRANCH_WEALTH[parent] * (0.4 + min(age, 65) / 40) * math.exp(wealth_z)
        annual_income = 9_0000 * income_mult * math.exp(r.normal(0, 0.55)) * BRANCH_WEALTH[parent]
        income_band = INCOME_BANDS[int(np.searchsorted([100_000, 300_000, 500_000, 1_000_000], annual_income, side="right"))]

        # 开户时间：老客户占多数，近两年有一批新客
        if r.random() < 0.16:
            open_date = date(2024, 11, 1) + timedelta(days=int(r.integers(0, 730)))
        else:
            open_date = date(2010, 1, 1) + timedelta(days=int(r.integers(0, 5400)))
        open_date = min(open_date, date(2026, 10, 20))

        pattern = r.choice(["稳定", "增长", "流失", "沉睡"], p=[0.66, 0.17, 0.065, 0.105])
        if open_date >= date(2024, 11, 1):
            pattern = "新客"

        totals = np.zeros(MONTHS)
        level_now = base
        for i, snap in enumerate(SNAPSHOTS):
            if snap < open_date:
                continue
            if pattern == "稳定":
                drift = r.normal(0.004, 0.035)
            elif pattern == "增长":
                drift = r.normal(0.035, 0.05)
            elif pattern == "流失":
                drift = r.normal(0.005, 0.03) if i < MONTHS - 6 else r.normal(-0.22, 0.08)
            elif pattern == "沉睡":
                drift = r.normal(-0.01, 0.01)
            else:  # 新客：首月入金后逐步沉淀
                months_in = sum(1 for s in SNAPSHOTS[: i + 1] if s >= open_date)
                drift = 0.25 if months_in <= 3 else r.normal(0.02, 0.04)
            # 季末冲存款、春节前揽储
            seasonal = 0.03 if snap.month in (3, 6, 9, 12) else 0.0
            seasonal += 0.04 if snap.month == 1 else 0.0
            level_now = max(level_now * (1 + drift), 50)
            totals[i] = level_now * (1 + seasonal)
        if pattern == "沉睡":
            totals = np.minimum(totals, 3000 + r.random() * 4000)
        if pattern == "新客":
            totals *= 0.6

        current = totals[-1]
        risk_base = 3.4 - (age - 40) / 25 + (0.6 if occupation in ("企业高管", "私营业主") else 0) + r.normal(0, 0.8)
        risk_level = f"C{int(np.clip(round(risk_base), 1, 5))}"
        risk_n = int(risk_level[1])
        # 资产配置：风险偏好越高、资产越多，存款占比越低
        dep = np.clip(0.85 - 0.11 * (risk_n - 1) - 0.06 * math.log10(max(current, 1e3) / 1e4) + r.normal(0, 0.08), 0.12, 0.98)
        rest = 1 - dep
        fund = rest * np.clip(0.12 * (risk_n - 1) + r.normal(0, 0.08), 0, 0.7)
        ins = rest * (np.clip(r.normal(0.18, 0.1), 0, 0.5) if age >= 30 and current > 100_000 else 0)
        wealth = max(rest - fund - ins, 0)

        level = level_of(current)
        branch_rms = rms[(rms.branch_id == branch.branch_id) & (rms.status == "在岗")]
        private_rms = rms[(rms.branch_id == parent_id) & (rms.status == "在岗")]
        if level in ("私行", "钻石") and len(private_rms) and r.random() < 0.85:
            rm_id = int(private_rms.rm_id.iloc[int(r.integers(len(private_rms)))])
        elif level in ("白金", "钻石", "私行") or (level == "金卡" and r.random() < 0.45):
            rm_id = int(branch_rms.rm_id.iloc[int(r.integers(len(branch_rms)))]) if len(branch_rms) else None
        else:
            rm_id = None

        rows.append(
            dict(
                customer_id=customer_id,
                customer_name=person_name(r),
                gender=gender,
                birth_date=birth,
                id_card_no=id_card(AREA_CODE[city], birth, r),
                mobile=mobile(r),
                city=city,
                branch_id=int(branch.branch_id),
                rm_id=rm_id,
                open_date=open_date,
                customer_level=level,
                occupation=occupation,
                annual_income_band=income_band,
                risk_level=risk_level,
                risk_assess_date=open_date + timedelta(days=int(r.integers(0, max((TODAY - open_date).days, 1)))),
                is_payroll=bool(occupation in ("企业职员", "公务员/事业单位", "专业人士(医生/律师/教师)", "企业高管") and r.random() < 0.55),
                preferred_channel=r.choice(["手机银行", "网点柜面", "客户经理", "微信银行"], p=[0.58, 0.14, 0.16, 0.12] if age < 60 else [0.25, 0.45, 0.2, 0.1]),
                marketing_consent=bool(r.random() < 0.82),
                customer_status="沉睡" if pattern == "沉睡" else "正常",
            )
        )
        trajectories[customer_id] = Trajectory(totals, dep, wealth, fund, ins, pattern)
    return pd.DataFrame(rows), trajectories


def build_aum(customers: pd.DataFrame, traj: dict[int, Trajectory]) -> pd.DataFrame:
    r = np.random.default_rng(SEED + 4)
    rows = []
    has_mortgage = {cid: r.random() < 0.18 for cid in customers.customer_id}
    for c in customers.itertuples():
        t = traj[c.customer_id]
        mortgage = r.uniform(400_000, 3_500_000) if has_mortgage[c.customer_id] else 0.0
        for i, snap in enumerate(SNAPSHOTS):
            total = float(t.totals[i]) if hasattr(t, "totals") else float(t.total[i])
            if total <= 0:
                continue
            jitter = r.normal(0, 0.03)
            dep = total * np.clip(t.deposit_share + jitter, 0.05, 1)
            fund = total * t.fund_share
            ins = total * t.insurance_share
            wealth = max(total - dep - fund - ins, 0)
            demand = dep * np.clip(0.35 + r.normal(0, 0.1), 0.1, 0.9)
            loan = mortgage * max(0.0, 1 - i / 400) if mortgage else 0.0
            rows.append(
                dict(
                    snapshot_month=snap,
                    customer_id=c.customer_id,
                    demand_deposit=round(demand, 2),
                    time_deposit=round(dep - demand, 2),
                    wealth_balance=round(wealth, 2),
                    fund_balance=round(fund, 2),
                    insurance_value=round(ins, 2),
                    total_aum=round(dep + wealth + fund + ins, 2),
                    loan_balance=round(loan, 2),
                )
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 账户、持仓、交易
# ---------------------------------------------------------------------------


def build_accounts(customers: pd.DataFrame) -> pd.DataFrame:
    r = np.random.default_rng(SEED + 5)
    rows = []
    aid = 6_222_000_000
    for c in customers.itertuples():
        aid += 1
        rows.append(dict(account_id=aid, customer_id=c.customer_id, account_type="I类借记卡", open_date=c.open_date, branch_id=c.branch_id, account_status="正常" if c.customer_status == "正常" else "久悬"))
        if r.random() < 0.3:
            aid += 1
            rows.append(dict(account_id=aid, customer_id=c.customer_id, account_type="II类电子账户", open_date=c.open_date + timedelta(days=int(r.integers(0, 400))), branch_id=c.branch_id, account_status="正常"))
        if c.customer_level != "普通" and r.random() < 0.5 or r.random() < 0.15:
            aid += 1
            rows.append(dict(account_id=aid, customer_id=c.customer_id, account_type="信用卡", open_date=c.open_date + timedelta(days=int(r.integers(30, 900))), branch_id=c.branch_id, account_status="正常" if r.random() < 0.95 else "销户"))
    df = pd.DataFrame(rows)
    df["open_date"] = df.open_date.clip(upper=TODAY)
    return df


def build_holdings(customers: pd.DataFrame, aum: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    r = np.random.default_rng(SEED + 6)
    latest = aum[aum.snapshot_month == SNAPSHOTS[-1]].set_index("customer_id")
    by_type = {t: g for t, g in products[products.status == "在售"].groupby("product_type")}
    rows = []
    hid = 1
    risk_order = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}

    def pick(ptype: str, risk_cap: int, allow_breach: bool):
        g = by_type[ptype]
        ok = g[g.risk_rating.map(risk_order) <= risk_cap]
        if allow_breach or ok.empty:
            ok = g
        return ok.iloc[int(r.integers(len(ok)))]

    for c in customers.itertuples():
        if c.customer_id not in latest.index:
            continue
        a = latest.loc[c.customer_id]
        cap = int(c.risk_level[1])
        breach = r.random() < 0.012  # 少量超风险等级持有，留作合规排查演示
        for ptype, balance, parts in (("定期存款", a.time_deposit * 0.7, 2), ("大额存单", a.time_deposit * 0.3, 1), ("理财产品", a.wealth_balance, 3), ("公募基金", a.fund_balance, 3), ("保险", a.insurance_value, 1)):
            if balance < 1000:
                continue
            if ptype == "大额存单" and balance < 200_000:
                continue
            k = int(r.integers(1, parts + 1))
            shares = r.dirichlet(np.ones(k))
            for s in shares:
                p = pick(ptype, cap, breach)
                term = int(p.term_days or 0)
                if term:
                    # 让一批到期日落在未来 60 天内，制造"到期承接"商机
                    if r.random() < 0.18:
                        maturity = TODAY + timedelta(days=int(r.integers(1, 60)))
                    else:
                        maturity = TODAY + timedelta(days=int(r.integers(60, max(term, 61))))
                    buy = maturity - timedelta(days=term)
                else:
                    buy = TODAY - timedelta(days=int(r.integers(10, 1500)))
                    maturity = None
                buy = max(buy, c.open_date)
                rows.append(dict(holding_id=hid, customer_id=c.customer_id, product_id=int(p.product_id), buy_date=buy, maturity_date=maturity, holding_amount=round(float(balance * s), 2), holding_status="持有中"))
                hid += 1
        # 已到期/已赎回的历史持仓
        for _ in range(int(r.poisson(0.8))):
            p = pick(r.choice(["定期存款", "理财产品", "公募基金"]), cap, False)
            buy = c.open_date + timedelta(days=int(r.integers(0, max((TODAY - c.open_date).days - 30, 1))))
            end = min(buy + timedelta(days=int(p.term_days or r.integers(60, 400))), TODAY - timedelta(days=1))
            rows.append(dict(holding_id=hid, customer_id=c.customer_id, product_id=int(p.product_id), buy_date=buy, maturity_date=end, holding_amount=round(float(r.lognormal(10.5, 1.0)), 2), holding_status=r.choice(["已到期", "已赎回"])))
            hid += 1
    return pd.DataFrame(rows)


TXN_TYPES_OUT = ["转出至他行", "转出至本行", "消费", "取现", "理财申购", "基金申购", "还款"]
MERCHANT = ["餐饮", "商超", "交通出行", "医疗", "教育", "旅游酒店", "数码家电", "缴费", "网购", "汽车", "房产家装"]


def build_transactions(customers: pd.DataFrame, accounts: pd.DataFrame, traj: dict[int, Trajectory]) -> pd.DataFrame:
    r = np.random.default_rng(SEED + 7)
    debit = accounts[accounts.account_type == "I类借记卡"].set_index("customer_id").account_id
    days = (TXN_END - TXN_START).days + 1
    rows = []
    tid = 1
    for c in customers.itertuples():
        t = traj[c.customer_id]
        if c.open_date > TXN_END:
            continue
        acct = int(debit.loc[c.customer_id])
        aum_now = max(float(t.total[-1]), 1000)
        activity = {"稳定": 1.0, "增长": 1.4, "流失": 0.9, "沉睡": 0.05, "新客": 1.2}[t.pattern]
        n = int(r.poisson(18 * activity * (0.6 + min(math.log10(aum_now) - 3, 3) / 3)))
        start = max(TXN_START, c.open_date)
        span = max((TXN_END - start).days, 1)
        # 代发工资：每月 10~15 日入账；流失客户最后 3 个月停发
        if c.is_payroll:
            salary = round(float(np.clip(r.lognormal(9.4, 0.5), 4000, 120000)), 2)
            m = date(start.year, start.month, 1)
            while m <= TXN_END:
                stop = t.pattern == "流失" and m >= date(2026, 8, 1)
                if not stop and m >= start:
                    when = datetime(m.year, m.month, int(r.integers(10, 16)), 9, int(r.integers(0, 60)))
                    rows.append((tid, acct, c.customer_id, when, "代发工资入账", "批量代发", salary, "本行"))
                    tid += 1
                m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        for _ in range(n):
            d = start + timedelta(days=int(r.integers(0, span)))
            when = datetime(d.year, d.month, d.day, int(r.integers(7, 23)), int(r.integers(0, 60)), int(r.integers(0, 60)))
            u = r.random()
            if u < 0.38:
                ttype, amount = "消费", r.lognormal(5.6, 1.1)
                cp = r.choice(MERCHANT)
            elif u < 0.52:
                ttype, amount, cp = "转入", r.lognormal(8.6, 1.3) * (aum_now / 2e5) ** 0.3, r.choice(["他行", "本行", "第三方支付"])
            elif u < 0.66:
                ttype, amount, cp = "转出至他行" if r.random() < 0.4 else "转出至本行", r.lognormal(8.4, 1.3) * (aum_now / 2e5) ** 0.3, "他行"
            elif u < 0.74:
                ttype, amount, cp = "理财申购", max(10000, aum_now * r.uniform(0.02, 0.15)), "本行"
            elif u < 0.80:
                ttype, amount, cp = "理财赎回", max(10000, aum_now * r.uniform(0.02, 0.12)), "本行"
            elif u < 0.86:
                ttype, amount, cp = "基金申购", r.lognormal(8.5, 1.0), "本行"
            elif u < 0.92:
                ttype, amount, cp = "取现", r.choice([500, 1000, 2000, 3000, 5000]), "ATM"
            else:
                ttype, amount, cp = "还款", r.lognormal(8.2, 0.8), "本行"
            if ttype == "转出至本行":
                cp = "本行"
            rows.append((tid, acct, c.customer_id, when, ttype, None, round(float(amount), 2), cp))
            tid += 1
        # 流失客户：近 5 个月的大额转出到他行
        if t.pattern == "流失":
            for k in range(int(r.integers(2, 6))):
                d = date(2026, 6, 1) + timedelta(days=int(r.integers(0, 150)))
                when = datetime(d.year, d.month, d.day, int(r.integers(9, 18)), int(r.integers(0, 60)))
                amount = max(float(t.total[-7]) * r.uniform(0.08, 0.3), 50_000)
                rows.append((tid, acct, c.customer_id, when, "转出至他行", None, round(amount, 2), "他行"))
                tid += 1
    df = pd.DataFrame(rows, columns=["txn_id", "account_id", "customer_id", "txn_time", "txn_type", "channel", "amount", "counterparty"])
    channels = np.array(["手机银行", "网上银行", "柜面", "ATM", "POS", "第三方支付"])
    p_by_type = {
        "消费": [0.35, 0.02, 0.0, 0.0, 0.33, 0.30],
        "取现": [0.0, 0.0, 0.15, 0.85, 0.0, 0.0],
    }
    default = [0.72, 0.1, 0.16, 0.0, 0.0, 0.02]
    missing = df.channel.isna()
    df.loc[missing, "channel"] = [channels[r.choice(6, p=p_by_type.get(tt, default))] for tt in df.loc[missing, "txn_type"]]
    df["direction"] = np.where(df.txn_type.isin(["转入", "代发工资入账", "理财赎回"]), "收入", "支出")
    df = df.sort_values("txn_time").reset_index(drop=True)
    df["txn_id"] = np.arange(1, len(df) + 1) + 900_000_000
    return df[["txn_id", "account_id", "customer_id", "txn_time", "txn_type", "direction", "channel", "amount", "counterparty"]]


# ---------------------------------------------------------------------------
# 营销：活动、名单与触达、转化
# ---------------------------------------------------------------------------

CAMPAIGNS = [
    # (名称, 类型, 目标产品类型, 开始, 结束, 主渠道, 目标客群规则, 预算)
    ("2025新春揽储·大额存单专享", "存款揽储", "大额存单", date(2025, 1, 6), date(2025, 2, 28), "客户经理面访", "aum>=300000", 800_000),
    ("一季度开门红·定期加息", "存款揽储", "定期存款", date(2025, 1, 2), date(2025, 3, 31), "短信", "aum>=50000", 300_000),
    ("理财到期承接·春季", "到期承接", "理财产品", date(2025, 3, 1), date(2025, 4, 30), "外呼", "wealth>0", 150_000),
    ("基金定投·五月开启计划", "基金定投", "公募基金", date(2025, 5, 6), date(2025, 6, 30), "APP推送", "risk>=3 & age<=50", 120_000),
    ("代发客户·工资理财", "理财销售", "理财产品", date(2025, 4, 1), date(2025, 6, 30), "APP推送", "payroll", 200_000),
    ("半年末存款冲刺", "存款揽储", "定期存款", date(2025, 6, 1), date(2025, 6, 30), "外呼", "aum>=100000", 260_000),
    ("养老理财·安心计划", "理财销售", "理财产品", date(2025, 7, 1), date(2025, 9, 30), "客户经理面访", "age>=50 & aum>=200000", 180_000),
    ("信用卡·年轻客群获客", "信用卡获客", "信用卡", date(2025, 7, 15), date(2025, 10, 15), "APP推送", "age<=35 & no_credit", 400_000),
    ("高净值客户·保险配置", "保险销售", "保险", date(2025, 8, 1), date(2025, 10, 31), "客户经理面访", "aum>=1000000", 220_000),
    ("三季度末存款冲刺", "存款揽储", "定期存款", date(2025, 9, 1), date(2025, 9, 30), "外呼", "aum>=100000", 240_000),
    ("沉睡客户唤醒", "客户促活", "活期存款", date(2025, 10, 8), date(2025, 12, 31), "短信", "dormant", 90_000),
    ("双十一·联名卡消费返现", "信用卡获客", "信用卡", date(2025, 10, 20), date(2025, 11, 30), "APP推送", "age<=45", 350_000),
    ("资金外流预警挽回·Q4", "流失挽回", "大额存单", date(2025, 11, 1), date(2025, 12, 31), "客户经理面访", "outflow", 160_000),
    ("年末存款冲刺", "存款揽储", "定期存款", date(2025, 12, 1), date(2025, 12, 31), "外呼", "aum>=100000", 300_000),
    ("2026新春揽储·新春专享大额存单", "存款揽储", "大额存单", date(2026, 1, 5), date(2026, 2, 28), "客户经理面访", "aum>=300000", 900_000),
    ("一季度开门红·财富焕新", "理财销售", "理财产品", date(2026, 1, 5), date(2026, 3, 31), "微信", "aum>=50000", 260_000),
    ("消费贷·春季焕新", "贷款营销", "个人贷款", date(2026, 3, 1), date(2026, 4, 30), "短信", "payroll & age<=45", 180_000),
    ("理财到期承接·春季", "到期承接", "理财产品", date(2026, 3, 1), date(2026, 4, 30), "外呼", "wealth>0", 150_000),
    ("基金定投·指数投资季", "基金定投", "公募基金", date(2026, 4, 1), date(2026, 5, 31), "APP推送", "risk>=3 & age<=50", 130_000),
    ("半年末存款冲刺", "存款揽储", "定期存款", date(2026, 6, 1), date(2026, 6, 30), "外呼", "aum>=100000", 280_000),
    ("代发客户·薪享理财", "理财销售", "理财产品", date(2026, 5, 6), date(2026, 7, 31), "APP推送", "payroll", 210_000),
    ("高净值客户·家族财富规划", "保险销售", "保险", date(2026, 6, 15), date(2026, 9, 30), "客户经理面访", "aum>=2000000", 260_000),
    ("资金外流预警挽回·Q3", "流失挽回", "大额存单", date(2026, 7, 1), date(2026, 9, 30), "客户经理面访", "outflow", 180_000),
    ("三季度末存款冲刺", "存款揽储", "定期存款", date(2026, 9, 1), date(2026, 9, 30), "外呼", "aum>=100000", 260_000),
    ("金秋理财节", "理财销售", "理财产品", date(2026, 9, 15), date(2026, 10, 31), "微信", "aum>=50000", 230_000),
    ("生日关怀·专属礼遇", "客户关怀", "活期存款", date(2026, 1, 1), date(2026, 12, 31), "短信", "birthday", 60_000),
    ("资金外流预警挽回·Q4", "流失挽回", "大额存单", date(2026, 10, 8), date(2026, 12, 31), "客户经理面访", "outflow", 200_000),
    ("到期承接·冬季大额存单", "到期承接", "大额存单", date(2026, 10, 20), date(2026, 12, 20), "外呼", "maturing", 220_000),
    ("年末存款冲刺", "存款揽储", "定期存款", date(2026, 11, 1), date(2026, 12, 31), "外呼", "aum>=100000", 320_000),
    ("信用卡·白金卡升级", "信用卡获客", "信用卡", date(2026, 11, 1), date(2026, 12, 31), "客户经理面访", "aum>=500000", 150_000),
]

#: 渠道的触达率与（触达后）成交率：面访最高，短信最低。
CHANNEL_RATES = {
    "客户经理面访": (0.78, 0.21),
    "外呼": (0.55, 0.085),
    "微信": (0.62, 0.05),
    "APP推送": (0.70, 0.032),
    "短信": (0.92, 0.012),
}


def eligible(rule: str, cust: pd.DataFrame, aum_then: pd.Series, holdings: pd.DataFrame, accounts: pd.DataFrame, patterns: dict[int, str]) -> pd.Series:
    age = (pd.Timestamp(TODAY) - pd.to_datetime(cust.birth_date)).dt.days // 365
    aum = cust.customer_id.map(aum_then).fillna(0)
    has_credit = cust.customer_id.isin(accounts[accounts.account_type == "信用卡"].customer_id)
    has_wealth = cust.customer_id.isin(holdings.merge(PRODUCTS_BY_ID, on="product_id").query("product_type == '理财产品'").customer_id)
    risk = cust.risk_level.str[1].astype(int)
    mask = pd.Series(True, index=cust.index)
    for clause in rule.split("&"):
        c = clause.strip()
        if c.startswith("aum>="):
            mask &= aum >= float(c[5:])
        elif c.startswith("age<="):
            mask &= age <= int(c[5:])
        elif c.startswith("age>="):
            mask &= age >= int(c[5:])
        elif c.startswith("risk>="):
            mask &= risk >= int(c[6:])
        elif c == "payroll":
            mask &= cust.is_payroll
        elif c == "no_credit":
            mask &= ~has_credit
        elif c == "wealth>0":
            mask &= has_wealth
        elif c == "dormant":
            mask &= cust.customer_status == "沉睡"
        elif c == "outflow":
            mask &= cust.customer_id.map(patterns).eq("流失") | (aum >= 200_000) & (cust.customer_id % 9 == 0)
        elif c == "birthday":
            mask &= True
        elif c == "maturing":
            soon = holdings[(holdings.holding_status == "持有中") & holdings.maturity_date.notna() & (pd.to_datetime(holdings.maturity_date) <= pd.Timestamp(TODAY + timedelta(days=60)))]
            mask &= cust.customer_id.isin(soon.customer_id)
    return mask & cust.marketing_consent


PRODUCTS_BY_ID = pd.DataFrame()


def build_marketing(customers, aum, holdings, accounts, products, rms, traj):
    global PRODUCTS_BY_ID
    PRODUCTS_BY_ID = products[["product_id", "product_type"]]
    r = np.random.default_rng(SEED + 8)
    patterns = {cid: t.pattern for cid, t in traj.items()}
    campaigns, targets, conversions = [], [], []
    tgt_id, conv_id = 1, 1
    snaps = pd.Series(SNAPSHOTS)
    in_stock = products[products.status == "在售"]
    for k, (name, ctype, ptype, start, end, channel, rule, budget) in enumerate(CAMPAIGNS, start=1):
        campaign_id = 5000 + k
        status = "已结束" if end < TODAY else "进行中" if start <= TODAY else "未开始"
        owner = None if k % 3 else 100 * (1 + k % 6)
        campaigns.append(dict(campaign_id=campaign_id, campaign_name=name if name.startswith(str(start.year)) or "2025" in name or "2026" in name else f"{start.year}{name}", campaign_type=ctype, target_product_type=ptype, start_date=start, end_date=end, main_channel=channel, target_rule=rule, budget=float(budget), owner_branch_id=owner, campaign_status=status))
        if start > TODAY:
            continue
        snap_idx = int(np.clip(snaps.searchsorted(pd.Timestamp(start)) - 1, 0, MONTHS - 1))
        aum_then = aum[aum.snapshot_month == SNAPSHOTS[snap_idx]].set_index("customer_id").total_aum
        pool = customers[customers.open_date <= start]
        mask = eligible(rule, pool, aum_then, holdings, accounts, patterns)
        if rule == "birthday":
            pool = pool[mask]
            pool = pool[pd.to_datetime(pool.birth_date).dt.month <= TODAY.month]
        else:
            pool = pool[mask]
        if owner:
            pool = pool[pool.branch_id // 100 * 100 == owner]
        size = min(len(pool), int(r.integers(600, 4500)) if channel == "客户经理面访" else int(r.integers(2000, 9000)))
        if size == 0:
            continue
        chosen = pool.sample(n=size, random_state=int(r.integers(1e9)))
        reach, convert = CHANNEL_RATES[channel]
        product_pool = in_stock[in_stock.product_type == ptype]
        last_day = min(end, TODAY - timedelta(days=1))
        span = max((last_day - start).days, 1)
        for c in chosen.itertuples():
            assign = start + timedelta(days=int(r.integers(0, min(span, 10) + 1)))
            reached = r.random() < reach
            # 有客户经理管户的客户，触达后更容易成交；高等级客户对面访更敏感
            boost = 1.0 + (0.6 if c.rm_id and channel in ("客户经理面访", "外呼") else 0) + (0.4 if c.customer_level in ("钻石", "私行") else 0)
            if patterns[c.customer_id] == "流失" and ctype != "流失挽回":
                boost *= 0.35
            if not reached:
                result, contact_time = "未触达", None
            else:
                contact = assign + timedelta(days=int(r.integers(0, span + 1)))
                contact = min(contact, last_day)
                contact_time = datetime(contact.year, contact.month, contact.day, int(r.integers(9, 20)), int(r.integers(0, 60)))
                u = r.random()
                p_conv = min(convert * boost, 0.6)
                if status == "进行中" and contact > TODAY - timedelta(days=7):
                    p_conv *= 0.4
                if u < p_conv:
                    result = "已成交"
                elif u < p_conv + 0.18:
                    result = "有意向"
                elif u < p_conv + 0.33:
                    result = "明确拒绝"
                else:
                    result = "已触达未响应"
            targets.append(dict(target_id=tgt_id, campaign_id=campaign_id, customer_id=c.customer_id, rm_id=c.rm_id if channel in ("客户经理面访", "外呼") else None, assign_date=assign, contact_channel=channel, contact_time=contact_time, contact_result=result))
            if result == "已成交" and len(product_pool):
                p = product_pool.iloc[int(r.integers(len(product_pool)))]
                aum_c = float(aum_then.get(c.customer_id, 10000))
                if ptype == "信用卡":
                    amount, revenue = 0.0, float(r.uniform(150, 600))
                elif ptype == "个人贷款":
                    amount = float(np.clip(r.lognormal(11.6, 0.6), 20_000, 500_000))
                    revenue = amount * 0.012
                elif ptype == "活期存款":
                    amount, revenue = float(r.lognormal(9.0, 1.0)), 0.0
                else:
                    amount = float(np.clip(aum_c * r.uniform(0.08, 0.45), float(p.min_amount) or 1000, 20_000_000))
                    fee = {"理财产品": 0.006, "公募基金": 0.012, "保险": 0.035, "大额存单": 0.0, "定期存款": 0.0}.get(ptype, 0.0)
                    revenue = amount * fee
                cdate = contact_time.date() + timedelta(days=int(r.integers(0, 6)))
                conversions.append(dict(conversion_id=conv_id, target_id=tgt_id, campaign_id=campaign_id, customer_id=c.customer_id, product_id=int(p.product_id), convert_date=min(cdate, TODAY), convert_amount=round(amount, 2), fee_income=round(revenue, 2), rm_id=c.rm_id))
                conv_id += 1
            tgt_id += 1
    return pd.DataFrame(campaigns), pd.DataFrame(targets), pd.DataFrame(conversions)


# ---------------------------------------------------------------------------
# 客户事件（商机）与标签
# ---------------------------------------------------------------------------


def build_events(customers, holdings, transactions, aum, products, traj):
    r = np.random.default_rng(SEED + 9)
    rows = []
    eid = 1
    ptypes = products.set_index("product_id").product_type
    soon = holdings[(holdings.holding_status == "持有中") & holdings.maturity_date.notna()]
    soon = soon[pd.to_datetime(soon.maturity_date) <= pd.Timestamp(TODAY + timedelta(days=60))]
    for h in soon.itertuples():
        t = ptypes[h.product_id]
        rows.append(dict(event_id=eid, customer_id=h.customer_id, event_type="定期到期" if t in ("定期存款", "大额存单") else "理财到期", event_date=h.maturity_date, related_amount=h.holding_amount, detail=f"持仓 {h.holding_id} 将于 {h.maturity_date} 到期"))
        eid += 1
    big = transactions[(transactions.txn_type == "转出至他行") & (transactions.amount >= 50_000) & (pd.to_datetime(transactions.txn_time) >= pd.Timestamp(date(2026, 5, 1)))]
    for t in big.itertuples():
        rows.append(dict(event_id=eid, customer_id=t.customer_id, event_type="大额资金转出", event_date=pd.Timestamp(t.txn_time).date(), related_amount=t.amount, detail="单笔转出至他行≥5万元"))
        eid += 1
    latest = aum[aum.snapshot_month == SNAPSHOTS[-1]].set_index("customer_id").total_aum
    before = aum[aum.snapshot_month == SNAPSHOTS[-4]].set_index("customer_id").total_aum
    drop = (latest / before).dropna()
    for cid, ratio in drop[(drop < 0.7) & (before.reindex(drop.index) >= 50_000)].items():
        rows.append(dict(event_id=eid, customer_id=int(cid), event_type="资产下滑", event_date=SNAPSHOTS[-1], related_amount=round(float(before[cid] - latest[cid]), 2), detail=f"近三个月 AUM 下降 {1 - ratio:.0%}"))
        eid += 1
    payroll = transactions[transactions.txn_type == "代发工资入账"]
    last_pay = payroll.groupby("customer_id").txn_time.max()
    stopped = last_pay[pd.to_datetime(last_pay) < pd.Timestamp(date(2026, 8, 1))]
    for cid, when in stopped.items():
        rows.append(dict(event_id=eid, customer_id=int(cid), event_type="代发停发", event_date=(pd.Timestamp(when) + pd.Timedelta(days=45)).date(), related_amount=None, detail="连续两个月以上未收到代发工资"))
        eid += 1
    for c in customers.itertuples():
        b = c.birth_date
        upcoming = date(TODAY.year, b.month, min(b.day, 28))
        if TODAY <= upcoming <= TODAY + timedelta(days=30) and c.customer_level != "普通":
            rows.append(dict(event_id=eid, customer_id=c.customer_id, event_type="客户生日", event_date=upcoming, related_amount=None, detail=f"{c.customer_level}客户生日"))
            eid += 1
    df = pd.DataFrame(rows)
    # 已处理：过去的事件大多已跟进，未来的未处理
    past = pd.to_datetime(df.event_date) < pd.Timestamp(TODAY)
    df["handle_status"] = np.where(past & (r.random(len(df)) < 0.62), "已跟进", "待跟进")
    return df


TAGS = [
    ("T01", "高净值潜力客户", "近12个月AUM增长超50%且当前AUM在30万至200万之间"),
    ("T02", "资金外流风险", "近三个月AUM下降超30%或存在大额转出至他行"),
    ("T03", "理财偏好", "理财产品持仓占AUM比例超40%"),
    ("T04", "基金投资者", "持有公募基金"),
    ("T05", "保障缺口", "AUM超100万且未持有任何保险"),
    ("T06", "代发工资客户", "近三个月有代发工资入账"),
    ("T07", "年轻客群", "年龄35岁及以下"),
    ("T08", "银发客群", "年龄60岁及以上"),
    ("T09", "房贷客户", "存在住房按揭贷款余额"),
    ("T10", "超风险持仓", "持有产品风险等级高于客户风险测评等级"),
    ("T11", "临近到期", "未来30天内有定期或理财到期"),
    ("T12", "数字化活跃", "近三个月手机银行交易超过10笔"),
]


def build_tags(customers, aum, holdings, products, transactions, events):
    rows = []
    latest = aum[aum.snapshot_month == SNAPSHOTS[-1]].set_index("customer_id")
    year_ago = aum[aum.snapshot_month == SNAPSHOTS[-13]].set_index("customer_id").total_aum
    age = ((pd.Timestamp(TODAY) - pd.to_datetime(customers.set_index("customer_id").birth_date)).dt.days // 365)
    hp = holdings[holdings.holding_status == "持有中"].merge(products[["product_id", "product_type", "risk_rating"]], on="product_id")
    risk_cust = customers.set_index("customer_id").risk_level.str[1].astype(int)
    hp["breach"] = hp.risk_rating.str[1].astype(int) > hp.customer_id.map(risk_cust)
    recent = transactions[pd.to_datetime(transactions.txn_time) >= pd.Timestamp(date(2026, 8, 1))]
    mobile_cnt = recent[recent.channel == "手机银行"].groupby("customer_id").size()
    payroll_recent = set(recent[recent.txn_type == "代发工资入账"].customer_id)
    ev = events.groupby("customer_id").event_type.agg(set)

    def add(cid, code, score):
        name = next(n for c, n, _ in TAGS if c == code)
        rows.append(dict(customer_id=int(cid), tag_code=code, tag_name=name, score=round(float(score), 2), tag_date=TODAY))

    for cid, a in latest.iterrows():
        growth = a.total_aum / year_ago.get(cid, np.nan) - 1 if year_ago.get(cid, 0) > 0 else np.nan
        if 300_000 <= a.total_aum < 2_000_000 and growth > 0.5:
            add(cid, "T01", min(growth, 3) / 3 * 100)
        e = ev.get(cid, set())
        if "资产下滑" in e or "大额资金转出" in e:
            add(cid, "T02", 90 if "资产下滑" in e and "大额资金转出" in e else 70)
        if a.total_aum > 0 and a.wealth_balance / a.total_aum > 0.4:
            add(cid, "T03", a.wealth_balance / a.total_aum * 100)
        if a.fund_balance > 0:
            add(cid, "T04", 60)
        if a.total_aum > 1_000_000 and a.insurance_value == 0:
            add(cid, "T05", 80)
        if cid in payroll_recent:
            add(cid, "T06", 100)
        if age.get(cid, 40) <= 35:
            add(cid, "T07", 100)
        if age.get(cid, 40) >= 60:
            add(cid, "T08", 100)
        if a.loan_balance > 0:
            add(cid, "T09", 100)
        if mobile_cnt.get(cid, 0) > 10:
            add(cid, "T12", min(mobile_cnt[cid], 60) / 60 * 100)
        if "定期到期" in e or "理财到期" in e:
            add(cid, "T11", 85)
    for cid in hp[hp.breach].customer_id.unique():
        add(cid, "T10", 95)
    return pd.DataFrame(rows), pd.DataFrame([dict(tag_code=c, tag_name=n, tag_rule=d) for c, n, d in TAGS])


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("out"))
    parser.add_argument("--customers", type=int, default=20_000)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    branches = build_branches()
    rms = build_rms(branches)
    products = build_products()
    customers, traj = build_customers(args.customers, branches, rms)
    aum = build_aum(customers, traj)
    accounts = build_accounts(customers)
    holdings = build_holdings(customers, aum, products)
    transactions = build_transactions(customers, accounts, traj)
    campaigns, targets, conversions = build_marketing(customers, aum, holdings, accounts, products, rms, traj)
    events = build_events(customers, holdings, transactions, aum, products, traj)
    tags, tag_dict = build_tags(customers, aum, holdings, products, transactions, events)

    tables = {
        "dim_branch": branches,
        "dim_relationship_manager": rms,
        "dim_product": products,
        "dim_customer": customers,
        "dim_customer_tag_def": tag_dict,
        "fact_account": accounts,
        "fact_aum_monthly": aum,
        "fact_holding": holdings,
        "fact_transaction": transactions,
        "mkt_campaign": campaigns,
        "mkt_campaign_target": targets,
        "mkt_conversion": conversions,
        "fact_customer_event": events,
        "fact_customer_tag": tags,
    }
    for name, df in tables.items():
        df.to_parquet(args.out / f"{name}.parquet", index=False)
        print(f"{name:28s} {len(df):>9,d} 行")


if __name__ == "__main__":
    main()
