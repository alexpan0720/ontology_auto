"""在本地 DuckDB 里载入生成的数据，检查业务分布，并跑通所有认证问答 SQL。

认证问答的 SQL 按 Databricks（Spark SQL）方言写，这里用 sqlglot 转成 DuckDB 方言执行，
保证导入 Databricks 前每条 SQL 都能出结果、结果有业务意义。

用法：
    python validate_local.py [--out ./out]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import sqlglot

HERE = Path(__file__).parent
SCHEMA = "bank_marketing"

CHECKS = {
    "客户等级分布与AUM占比": """
        SELECT c.customer_level, count(*) AS customers,
               round(sum(a.total_aum) / 1e8, 2) AS aum_yi,
               round(100 * sum(a.total_aum) / sum(sum(a.total_aum)) OVER (), 1) AS aum_pct
        FROM bank_marketing.dim_customer c
        JOIN bank_marketing.fact_aum_monthly a ON a.customer_id = c.customer_id AND a.snapshot_month = DATE'2026-10-31'
        GROUP BY 1 ORDER BY aum_yi DESC""",
    "全行AUM月度趋势(亿元)": """
        SELECT snapshot_month, round(sum(total_aum) / 1e8, 2) AS aum_yi, count(*) AS customers
        FROM bank_marketing.fact_aum_monthly GROUP BY 1 ORDER BY 1""",
    "各渠道营销转化率": """
        SELECT contact_channel, count(*) AS targets,
               round(100 * avg(CASE WHEN contact_result <> '未触达' THEN 1 ELSE 0 END), 1) AS reach_pct,
               round(100 * avg(CASE WHEN contact_result = '已成交' THEN 1 ELSE 0 END), 2) AS convert_pct
        FROM bank_marketing.mkt_campaign_target GROUP BY 1 ORDER BY convert_pct DESC""",
    "事件类型分布": """
        SELECT event_type, handle_status, count(*) AS n FROM bank_marketing.fact_customer_event GROUP BY 1, 2 ORDER BY 1, 2""",
    "标签覆盖": """
        SELECT tag_name, count(*) AS customers FROM bank_marketing.fact_customer_tag GROUP BY 1 ORDER BY 2 DESC""",
    "交易类型": """
        SELECT txn_type, count(*) AS n, round(sum(amount) / 1e8, 2) AS amount_yi FROM bank_marketing.fact_transaction GROUP BY 1 ORDER BY 2 DESC""",
}


def load(con: duckdb.DuckDBPyConnection, out: Path) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    for file in sorted(out.glob("*.parquet")):
        con.execute(f"CREATE OR REPLACE TABLE {SCHEMA}.{file.stem} AS SELECT * FROM read_parquet('{file.as_posix()}')")


def run(con: duckdb.DuckDBPyConnection, sql: str, *, spark: bool = False):
    if spark:
        # DuckDB has no `workspace` catalog: the schema is attached at the top level.
        sql = sqlglot.transpile(sql.replace("workspace.bank_marketing.", "bank_marketing."), read="databricks", write="duckdb")[0]
    return con.execute(sql).fetchdf()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument("--checks", action="store_true", help="打印业务分布检查")
    args = parser.parse_args()
    con = duckdb.connect()
    load(con, args.out)

    if args.checks:
        for title, sql in CHECKS.items():
            print(f"\n== {title}")
            print(run(con, sql).to_string(index=False))

    qa_file = HERE / "verified_queries.json"
    if qa_file.exists():
        failures = 0
        for item in json.loads(qa_file.read_text(encoding="utf-8")):
            try:
                df = run(con, item["sql"], spark=True)
                status = f"{len(df)} 行" if len(df) else "空结果!"
                if not len(df):
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - report every failing query
                status, failures = f"失败: {exc}", failures + 1
            print(f"[{status}] {item['question']}")
            if args.checks and len(df):
                print(df.head(5).to_string(index=False))
        print(f"\n认证问答失败或为空：{failures}")


if __name__ == "__main__":
    main()
