"""Render the article's illustrations to PNG with headless Edge.

Usage: python build_images.py   (writes ../images/*.png)
"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "images"
TMP = HERE / "_html"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:900px;overflow:hidden;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#0f172a;background:#fff}
.wrap{width:900px;padding:36px 40px}
.h{font-size:26px;font-weight:700;letter-spacing:1px}
.sub{font-size:15px;color:#64748b;margin-top:6px}
.blue{color:#2563eb}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 4px 14px rgba(15,23,42,.06)}
.tag{display:inline-block;font-size:13px;padding:3px 10px;border-radius:999px;background:#eff6ff;color:#1d4ed8;margin:3px 4px 0 0}
.mono{font-family:Consolas,"Cascadia Mono",monospace}
"""

IMAGES: dict[str, tuple[int, str]] = {}

# ---------------------------------------------------------------- cover
IMAGES["00-cover"] = (383, """
<div style="width:900px;height:383px;position:relative;overflow:hidden;
 background:radial-gradient(circle at 80% 30%,#1e40af 0,#0b1530 55%,#060b1a 100%);color:#fff">
 <svg width="900" height="383" style="position:absolute;left:0;top:0;opacity:.55">
  <g stroke="#60a5fa" stroke-width="1.4" fill="none">
   <line x1="610" y1="90" x2="720" y2="150"/><line x1="720" y1="150" x2="820" y2="95"/>
   <line x1="720" y1="150" x2="700" y2="260"/><line x1="700" y1="260" x2="820" y2="300"/>
   <line x1="610" y1="90" x2="580" y2="210"/><line x1="580" y1="210" x2="700" y2="260"/>
   <line x1="820" y1="95" x2="860" y2="200"/><line x1="860" y1="200" x2="820" y2="300"/>
   <line x1="580" y1="210" x2="520" y2="320"/>
  </g>
  <g fill="#93c5fd">
   <circle cx="610" cy="90" r="7"/><circle cx="720" cy="150" r="11" fill="#fff"/>
   <circle cx="820" cy="95" r="6"/><circle cx="700" cy="260" r="9"/>
   <circle cx="820" cy="300" r="6"/><circle cx="580" cy="210" r="7"/>
   <circle cx="860" cy="200" r="5"/><circle cx="520" cy="320" r="5"/>
  </g>
 </svg>
 <div style="position:absolute;left:48px;top:62px">
  <div style="font-size:15px;letter-spacing:3px;color:#93c5fd">开源 · 企业数据语义层</div>
  <div style="font-size:44px;font-weight:800;line-height:1.3;margin-top:14px">一句话问数<br>让数据听懂“人话”</div>
  <div style="font-size:17px;color:#cbd5e1;margin-top:20px">alexpan 本体 —— 自动构建业务本体 · 智能问数 · 数据治理</div>
  <div style="margin-top:22px">
   <span style="font-size:13px;padding:5px 12px;border:1px solid #3b82f6;border-radius:999px;margin-right:8px;color:#bfdbfe">Text-to-SQL</span>
   <span style="font-size:13px;padding:5px 12px;border:1px solid #3b82f6;border-radius:999px;margin-right:8px;color:#bfdbfe">钉钉 / 飞书机器人</span>
   <span style="font-size:13px;padding:5px 12px;border:1px solid #3b82f6;border-radius:999px;color:#bfdbfe">MCP</span>
  </div>
 </div>
</div>
""")

# ---------------------------------------------------------------- ontology concept
IMAGES["01-ontology"] = (420, """
<div class="wrap" style="background:#f8fafc;height:420px">
 <div class="h">从“表和字段”到“业务语言”</div>
 <div class="sub">本体（语义层）把数据库里的技术细节，翻译成人和 AI 都能理解的业务概念</div>
 <div style="display:flex;align-items:center;gap:14px;margin-top:26px">
  <div class="card" style="width:240px;padding:16px">
   <div style="font-weight:700;font-size:15px;margin-bottom:10px">🗄️ 原始数据库</div>
   <div class="mono" style="font-size:13px;line-height:1.9;color:#475569">
    ods_ord_dtl<br>&nbsp; pay_amt, st_cd, rgn_id<br>dim_rgn<br>&nbsp; rgn_id, rgn_nm<br>t_usr_info<br>&nbsp; uid, reg_dt, mob_no
   </div>
  </div>
  <div style="font-size:30px;color:#94a3b8">➜</div>
  <div class="card" style="width:300px;padding:16px;border:2px solid #2563eb">
   <div style="font-weight:700;font-size:15px;margin-bottom:10px" class="blue">🧠 本体 / 语义层</div>
   <div style="font-size:13.5px;line-height:1.75">
    <b>实体</b>：订单、用户、大区<br>
    <b>关系</b>：订单 → 大区（语义外键）<br>
    <b>术语</b>：销售额 = Σ 支付金额<br>
    <span style="color:#64748b">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp;（仅已支付订单）</span><br>
    <b>敏感字段</b>：手机号 · 自动识别 PII
   </div>
  </div>
  <div style="font-size:30px;color:#94a3b8">➜</div>
  <div style="width:170px">
   <div class="card" style="padding:12px;margin-bottom:12px;text-align:center;font-size:14px">🙋 业务人员<br><span style="color:#64748b;font-size:12px">自然语言提问</span></div>
   <div class="card" style="padding:12px;text-align:center;font-size:14px">🤖 AI Agent<br><span style="color:#64748b;font-size:12px">MCP / API 调用</span></div>
  </div>
 </div>
 <div style="margin-top:26px;font-size:13px;color:#64748b;text-align:center">采集元数据 → 抽取主外键、语义外键与业务术语 → 生成向量，存入 Postgres（pgvector）</div>
</div>
""")

# ---------------------------------------------------------------- pipeline
steps = [
    ("💬", "提问", "“上个月华东区<br>销售额多少？”"),
    ("🔎", "检索候选表", "向量检索 +<br>重排序"),
    ("🏷️", "实体与术语", "华东 → 大区<br>销售额 → 口径"),
    ("🧩", "生成 SQL", "生成 + 校验<br>权限检查"),
    ("🛠️", "执行与修复", "空结果时<br>自动修复重试"),
    ("📊", "图表 + 溯源", "自动出图<br>标注来源"),
]
step_html = "".join(
    f"""<div style="width:118px;text-align:center">
     <div style="width:64px;height:64px;margin:0 auto;border-radius:18px;background:{'#2563eb' if i in (0,5) else '#eff6ff'};
       font-size:28px;line-height:64px">{ic}</div>
     <div style="font-weight:700;font-size:15px;margin-top:10px">{t}</div>
     <div style="font-size:12.5px;color:#64748b;margin-top:6px;line-height:1.55">{d}</div></div>"""
    + ("" if i == len(steps) - 1 else '<div style="color:#93c5fd;font-size:20px;margin-top:20px">›</div>')
    for i, (ic, t, d) in enumerate(steps)
)
IMAGES["02-pipeline"] = (300, f"""
<div class="wrap" style="height:300px">
 <div class="h">一个问题背后的多阶段 Agent 流水线</div>
 <div class="sub">基于 LangGraph 编排，每一步都可追溯</div>
 <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:32px">{step_html}</div>
</div>
""")

# ---------------------------------------------------------------- architecture
def box(t, d, bg="#fff", bd="#cbd5e1", w=None):
    ws = f"width:{w}px;" if w else ""
    return (f'<div style="{ws}background:{bg};border:1.5px solid {bd};border-radius:12px;padding:10px 12px;text-align:center">'
            f'<div style="font-weight:700;font-size:14.5px">{t}</div><div style="font-size:12px;color:#64748b;margin-top:3px;line-height:1.5">{d}</div></div>')

IMAGES["03-arch"] = (560, f"""
<div class="wrap" style="height:560px;background:#f8fafc">
 <div class="h">整体架构</div>
 <div class="sub">Docker Compose 一键启动，对外只需开放 3000 端口</div>
 <div style="display:flex;gap:12px;margin-top:22px">
  {box("🌐 Web 界面", "问数 / 目录 / 设置", w=200)}{box("💬 钉钉 / 飞书", "群聊 @机器人 追问", w=200)}
  {box("🔌 MCP · REST API", "Cursor、Claude 等 Agent", w=200)}{box("⏰ 订阅与预警", "定时推送到群", w=180)}
 </div>
 <div style="text-align:center;color:#94a3b8;font-size:18px;margin:6px 0">▼</div>
 {box("Next.js 网关", "账号体系 · RBAC · SSO · API Token", bg="#eff6ff", bd="#93c5fd")}
 <div style="text-align:center;color:#94a3b8;font-size:18px;margin:6px 0">▼</div>
 <div style="display:flex;gap:12px;align-items:stretch">
  <div style="flex:1">{box("FastAPI 问数后端", "LangGraph 多阶段 Agent · 认证问答库 · 问数质量", bg="#2563eb22", bd="#2563eb")}</div>
  <div style="flex:1">{box("采集服务", "元数据采集 · PII 识别 · 语义编译 · 向量化", bg="#2563eb22", bd="#2563eb")}</div>
 </div>
 <div style="display:flex;gap:12px;margin-top:12px">
  <div style="flex:1">{box("🐘 Postgres + pgvector", "本体 · 目录 · 向量 · 审计")}</div>
  <div style="flex:1">{box("🧠 大模型（OpenAI 兼容）", "硅基流动 · DeepSeek · NVIDIA NIM")}</div>
 </div>
 <div style="margin-top:12px;background:#fff7ed;border:1.5px solid #fdba74;border-radius:12px;padding:10px 14px;text-align:center">
  <div style="font-weight:700;font-size:14.5px">🛡️ 治理层（连接器统一拦截）→ 源数据库</div>
  <div style="font-size:12px;color:#9a3412;margin-top:4px">Postgres · MySQL · Snowflake · Databricks · ClickHouse · Trino · Kyuubi · DuckDB · SQLite · HeavyDB</div>
 </div>
</div>
""")

# ---------------------------------------------------------------- governance
def gov(title, color, desc, table):
    return f"""<div class="card" style="flex:1;padding:16px;border-top:4px solid {color}">
     <div style="font-weight:700;font-size:16px">{title}</div><div style="font-size:12.5px;color:#64748b;margin:6px 0 12px;line-height:1.6;height:40px">{desc}</div>
     <table style="width:100%;border-collapse:collapse;font-size:12.5px">{table}</table></div>"""

td = 'style="border:1px solid #e2e8f0;padding:5px 6px"'
IMAGES["05-governance"] = (400, f"""
<div class="wrap" style="height:400px;background:#f8fafc">
 <div class="h">同一张表，不同的人看到不同的数据</div>
 <div class="sub">按用户组配置，在数据库连接器层统一强制执行</div>
 <div style="display:flex;gap:14px;margin-top:22px">
  {gov("🚫 列策略", "#ef4444", "禁止读取指定字段，任何位置引用（含 SELECT *）都拒绝",
   f'<tr><td {td}>姓名</td><td {td}>城市</td><td style="background:#fee2e2;border:1px solid #e2e8f0;padding:5px 6px;color:#b91c1c">身份证 ✕</td></tr><tr><td {td}>张三</td><td {td}>杭州</td><td style="background:#fee2e2;border:1px solid #e2e8f0;padding:5px 6px">—</td></tr><tr><td {td}>李四</td><td {td}>广州</td><td style="background:#fee2e2;border:1px solid #e2e8f0;padding:5px 6px">—</td></tr>')}
  {gov("🔍 行策略", "#2563eb", "把表改写为带过滤条件的子查询，只返回有权看到的行",
   f'<tr><td {td}>订单</td><td {td}>大区</td><td {td}>金额</td></tr><tr><td {td}>#1001</td><td {td}>华东</td><td {td}>¥320</td></tr><tr><td {td}>#1004</td><td {td}>华东</td><td {td}>¥158</td></tr>')}
  {gov("🎭 脱敏策略", "#f59e0b", "查询、分组、过滤、关联中都只能看到脱敏后的值",
   f'<tr><td {td}>用户</td><td {td}>手机号</td></tr><tr><td {td}>张三</td><td {td}>138****5678</td></tr><tr><td {td}>李四</td><td {td}>139****0021</td></tr>')}
 </div>
 <div style="display:flex;gap:10px;margin-top:20px;font-size:13px;color:#334155;justify-content:center">
  <span class="tag">👥 用户组</span><span class="tag">📝 权限申请与审批</span><span class="tag">📜 访问审计</span><span class="tag">🔒 无法判定安全的 SQL 一律拒绝</span>
 </div>
</div>
""")

# ---------------------------------------------------------------- IM bot
def msg(who, avatar, text, me=False):
    if me:
        return f"""<div style="display:flex;justify-content:flex-end;gap:8px;margin:12px 0"><div style="max-width:300px"><div style="font-size:11px;color:#94a3b8;text-align:right">{who}</div>
          <div style="background:#d6e8ff;padding:8px 12px;border-radius:10px;font-size:13.5px;line-height:1.6;margin-top:2px">{text}</div></div>
          <div style="width:34px;height:34px;border-radius:8px;background:#f59e0b;color:#fff;font-size:14px;line-height:34px;text-align:center">{avatar}</div></div>"""
    return f"""<div style="display:flex;gap:8px;margin:12px 0"><div style="width:34px;height:34px;border-radius:8px;background:#2563eb;color:#fff;font-size:14px;line-height:34px;text-align:center">{avatar}</div>
       <div style="max-width:300px"><div style="font-size:11px;color:#94a3b8">{who}</div>
       <div style="background:#fff;padding:8px 12px;border-radius:10px;font-size:13.5px;line-height:1.6;margin-top:2px">{text}</div></div></div>"""

phone = (
    msg("王经理", "王", "@问数助手 本周新增注册用户有多少？", me=True)
    + msg("问数助手", "AP", "本周新增注册用户 <b>3,482</b> 人，较上周 ▲12.4%。<br><span style='color:#64748b;font-size:12px'>数据来源：users.register_at</span>")
    + msg("王经理", "王", "那华东呢？", me=True)
    + msg("问数助手", "AP", "<span style='color:#64748b'>理解为：本周华东区新增注册用户数</span><br>华东区 <b>1,206</b> 人，占全部 34.6%。")
)
IMAGES["06-bot"] = (530, f"""
<div style="width:900px;height:530px;background:linear-gradient(135deg,#eff6ff,#f8fafc);display:flex;align-items:center;justify-content:center;gap:46px">
 <div style="width:390px;height:470px;background:#f1f5f9;border:10px solid #0f172a;border-radius:38px;overflow:hidden">
  <div style="background:#fff;height:50px;line-height:50px;text-align:center;font-weight:700;font-size:15px;border-bottom:1px solid #e2e8f0">销售运营群（28）</div>
  <div style="padding:6px 14px">{phone}</div>
 </div>
 <div style="width:330px">
  <div class="h" style="font-size:24px">在工作群里直接问数</div>
  <div style="font-size:14.5px;line-height:2;margin-top:16px;color:#334155">
   ✅ 钉钉、飞书均支持，群聊 @ 或私聊<br>
   ✅ 支持多轮追问，先复述“理解为”<br>
   ✅ 按提问人账号的权限执行查询<br>
   ✅ 脱敏、审计与 Web 端完全一致<br>
   ✅ Stream 长连接，<b>无需公网地址</b>
  </div>
 </div>
</div>
""")

# ---------------------------------------------------------------- subscription
IMAGES["07-alert"] = (360, """
<div style="width:900px;height:360px;background:#f8fafc;display:flex;align-items:center;justify-content:center;gap:40px">
 <div style="width:360px">
  <div class="h" style="font-size:24px">指标订阅与预警</div>
  <div style="font-size:14.5px;line-height:2;margin-top:16px;color:#334155">
   ⏰ 工作日 / 每天 / 每周 / 每小时<br>
   📌 只用<b>认证过的口径 SQL</b><br>
   📈 阈值预警、较上次变化预警<br>
   🔕 可设为“只在触发预警时推送”<br>
   🧪 支持试运行与立即推送
  </div>
 </div>
 <div class="card" style="width:400px;padding:0;overflow:hidden">
  <div style="background:#fef2f2;color:#b91c1c;padding:12px 18px;font-weight:700;font-size:15px">⚠️ 预警 · 每日销售额</div>
  <div style="padding:16px 18px;font-size:14px;line-height:1.9">
   <div style="color:#64748b;font-size:12.5px">工作日 09:00 · 来自认证问答库</div>
   <div style="font-size:30px;font-weight:800;margin:4px 0">¥1,284,300</div>
   <div>较上次 <b style="color:#dc2626">▼ 18.6%</b>（预警线：下降超过 15%）</div>
   <div style="border-top:1px dashed #e2e8f0;margin-top:10px;padding-top:8px;font-size:12.5px;color:#64748b">按普通用户权限查询，敏感字段已脱敏 · 已记入访问审计</div>
  </div>
 </div>
</div>
""")

# ---------------------------------------------------------------- quality loop
loop = [("💬", "用户提问", "Web / 机器人"), ("👍👎", "反馈与失败", "差评 · 报错 · 无数据 · 被拦截"),
        ("📋", "问数质量看板", "同义问题合并，按次数排序"), ("✍️", "补充认证问答", "沉淀标准口径 SQL")]
loop_html = "".join(
    f"""<div style="width:170px;text-align:center"><div style="width:76px;height:76px;margin:0 auto;border-radius:50%;background:#fff;border:2px solid #2563eb;font-size:26px;line-height:72px">{ic}</div>
     <div style="font-weight:700;font-size:15px;margin-top:10px">{t}</div><div style="font-size:12.5px;color:#64748b;margin-top:4px;line-height:1.5">{d}</div></div>"""
    + ('<div style="color:#2563eb;font-size:22px;margin-top:24px">→</div>' if i < 3 else "")
    for i, (ic, t, d) in enumerate(loop)
)
IMAGES["08-loop"] = (340, f"""
<div class="wrap" style="height:340px;background:#f8fafc">
 <div class="h">越用越准的质量闭环</div>
 <div class="sub">没答好的问题不会石沉大海</div>
 <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:30px">{loop_html}</div>
 <div style="margin:22px auto 0;width:620px;border:2px dashed #93c5fd;border-top:none;height:22px;border-radius:0 0 18px 18px;position:relative">
  <div style="position:absolute;left:50%;transform:translateX(-50%);bottom:-12px;background:#f8fafc;padding:0 10px;font-size:13px;color:#2563eb">相似问题自动参考认证 SQL，回答更准</div></div>
</div>
""")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    for name, (height, body) in IMAGES.items():
        html = TMP / f"{name}.html"
        html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body>{body}</body></html>",
                        encoding="utf-8")
        png = OUT / f"{name}.png"
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        f"--window-size=900,{height}", f"--screenshot={png}", html.as_uri()],
                       check=True, capture_output=True)
        print("wrote", png)


if __name__ == "__main__":
    main()
