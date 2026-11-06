"""把生成的 Parquet 导入 Databricks Unity Catalog。

步骤：建 schema 和 Volume → 用 Files API 上传 Parquet → 按 schema.py 建表（带中文
注释与主键）→ 用 read_files 批量写入（按目标类型转换）→ 补外键 → 核对行数。

连接信息取自平台里已保存的 Databricks 连接（catalog_database.connection），
需要能访问平台的 Postgres，在 auto-ontology 目录下这样运行：

    uv run --env-file .env python ../databricks_demo/bank_marketing/load_databricks.py \
        [--catalog workspace] [--schema bank_marketing] [--out ../databricks_demo/bank_marketing/out]

token 只在内存里使用，不会打印。
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from schema import SCHEMA_COMMENT, TABLES, create_table_sql, foreign_key_sql, insert_sql  # noqa: E402


def saved_connection() -> dict:
    from auto_ontology.dal.connections import list_connections

    found = [c for c in list_connections() if c.get("type") == "databricks"]
    if not found:
        raise SystemExit("平台里没有已保存的 Databricks 连接")
    return found[0]


def upload(host: str, token: str, volume_path: str, file: Path) -> None:
    url = f"https://{host}/api/2.0/fs/files{volume_path}?overwrite=true"
    req = urllib.request.Request(
        url,
        data=file.read_bytes(),
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    try:
        urllib.request.urlopen(req, timeout=600).read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"上传 {file.name} 失败：{exc.code} {exc.read()[:300]!r}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", default="bank_marketing")
    parser.add_argument("--out", type=Path, default=HERE / "out")
    args = parser.parse_args()

    from databricks import sql as dbsql

    conn_info = saved_connection()
    host, token, http_path = conn_info["host"], conn_info["password"], conn_info["http_path"]
    volume = f"/Volumes/{args.catalog}/{args.schema}/raw"

    with dbsql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
        cur = conn.cursor()

        def run(statement: str) -> None:
            cur.execute(statement)

        print("建 schema 与 Volume…")
        run(f"USE CATALOG {args.catalog}")
        run(f"CREATE SCHEMA IF NOT EXISTS {args.schema} COMMENT '{SCHEMA_COMMENT}'")
        run(f"USE SCHEMA {args.schema}")
        run("CREATE VOLUME IF NOT EXISTS raw COMMENT '演示数据的 Parquet 原始文件'")

        for table in TABLES:
            file = args.out / f"{table.name}.parquet"
            print(f"上传 {file.name} ({file.stat().st_size / 1e6:.1f} MB)…")
            upload(host, token, f"{volume}/{file.name}", file)

        print("建表并导入…")
        for table in reversed(TABLES):
            run(f"DROP TABLE IF EXISTS {table.name}")
        for table in TABLES:
            run(create_table_sql(table))
            run(insert_sql(table, f"read_files('{volume}/{table.name}.parquet', format => 'parquet')"))
            cur.execute(f"SELECT count(*) FROM {table.name}")
            print(f"  {table.name:28s} {cur.fetchone()[0]:>9,d} 行")
        for table in TABLES:
            for statement in foreign_key_sql(table):
                run(statement)
        print("完成。")


if __name__ == "__main__":
    main()
