"""向平台提问并打印回答：演示前用来验证问数效果。

    python ask.py "上海分行有多少私行客户？" ["第二个问题" ...]

不带参数时依次问一组演示问题。调用后端的问数接口（无会话、按管理员身份），
打印生成的 SQL、回答和耗时。管理员 id 从平台数据库读取，在 auto-ontology 目录下运行：

    uv run --env-file .env python ../databricks_demo/bank_marketing/ask.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

API = "http://localhost:3001/api/chat/completions"

DEMO_QUESTIONS = [
    "截至10月末，全行零售AUM是多少？各客户等级的AUM占比如何？",
    "上海分行有多少私行客户？他们的AUM合计是多少？",
    "哪个触达渠道的营销转化率最高？",
    "未来30天有多少理财和定期要到期？按分行看",
    "近三个月AUM下降超过30%的客户有多少？主要集中在哪些分行？",
    "2026年中收贡献最高的营销活动是哪个？",
    "代发工资客户的理财持有率是多少？",
    "有没有客户买了超过自己风险等级的产品？",
]


def admin_id() -> str:
    from auto_ontology.dal.session import store

    return store().query_read(
        "SELECT id FROM frontend.\"user\" WHERE role = 'admin' ORDER BY \"createdAt\" LIMIT 1"
    )[0]["id"]


def ask(question: str, user_id: str) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps({"question": question}, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream",
            "x-auto-ontology-user-id": user_id,
        },
    )
    out: dict = {"sql": None, "answer": "", "rows": None, "error": None}
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            data = json.loads(line[5:])
            if data.get("type") == "sql":
                out["sql"] = data.get("sql")
            elif data.get("type") == "result":
                answer = data.get("answer") or {}
                out["sql"] = answer.get("sql_code") or out["sql"]
                out["answer"] = answer.get("response") or ""
                out["rows"] = answer.get("sql_response_from_db")
            elif data.get("type") == "error":
                out["error"] = data.get("message") or data
    return out


def main() -> None:
    user = admin_id()
    for question in sys.argv[1:] or DEMO_QUESTIONS:
        started = time.time()
        try:
            result = ask(question, user)
        except Exception as exc:  # noqa: BLE001 - report and go on to the next
            print(f"\n### {question}\n失败：{exc}")
            continue
        print(f"\n### {question}  （{time.time() - started:.0f} 秒）")
        if result["error"]:
            print(f"错误: {result['error']}")
        print(f"SQL: {result['sql']}")
        print(f"回答: {result['answer'][:600]}")
        if result["rows"]:
            print(f"结果: {str(result['rows'])[:600]}")


if __name__ == "__main__":
    main()
