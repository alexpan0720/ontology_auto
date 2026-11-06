"""建三个演示账号并加入对应用户组，用来演示行级权限和脱敏。

    总行零售分析师   → 总行零售管理部（全行客户，明文）
    上海分行客户经理 → 上海分行零售团队（只看上海分行，敏感信息脱敏）
    北京分行客户经理 → 北京分行零售团队（只看北京分行，敏感信息脱敏）

账号为普通用户（viewer），用邮箱密码登录。密码随机生成，写入同目录的
demo_accounts.local.json（已被 .gitignore 忽略，不要提交或外发）；已存在的账号
保留原密码。哈希用 Better Auth 自己的 hashPassword（通过前端的 node_modules），
与正常登录流程一致。只用于本地或测试环境。

在 auto-ontology 目录下运行：

    uv run --env-file .env python ../databricks_demo/bank_marketing/create_demo_users.py
"""

from __future__ import annotations

import json
import secrets
import subprocess
import uuid
from pathlib import Path

HERE = Path(__file__).parent
FRONTEND = HERE.parent.parent / "auto-ontology" / "frontend"
ACCOUNTS_FILE = HERE / "demo_accounts.local.json"

USERS = [
    ("zh.analyst@bank-demo.test", "总行零售分析师", "总行零售管理部"),
    ("sh.rm@bank-demo.test", "上海分行客户经理", "上海分行零售团队"),
    ("bj.rm@bank-demo.test", "北京分行客户经理", "北京分行零售团队"),
]


def hash_password(password: str) -> str:
    script = "import('better-auth/crypto').then(async (m) => process.stdout.write(await m.hashPassword(process.argv[1])))"
    out = subprocess.run(
        ["node", "-e", script, password],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    return out.stdout.strip()


def main() -> None:
    from auto_ontology.dal.session import store, write_transaction

    saved = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8")) if ACCOUNTS_FILE.exists() else {}
    user_ids: dict[str, str] = {}
    for email, name, _group in USERS:
        found = store().query_read('SELECT id FROM frontend."user" WHERE email = :email', {"email": email})
        if found:
            user_ids[email] = found[0]["id"]
            continue
        password = secrets.token_urlsafe(12)
        hashed = hash_password(password)
        user_id = str(uuid.uuid4())
        with write_transaction():
            store().query_write(
                'INSERT INTO frontend."user" (id, name, email, "emailVerified", role, "createdAt", "updatedAt") '
                "VALUES (:id, :name, :email, true, 'viewer', now(), now())",
                {"id": user_id, "name": name, "email": email},
            )
            store().query_write(
                'INSERT INTO frontend.account (id, "accountId", "providerId", "userId", password, "createdAt", "updatedAt") '
                "VALUES (:id, :uid, 'credential', :uid, :password, now(), now())",
                {"id": str(uuid.uuid4()), "uid": user_id, "password": hashed},
            )
        saved[email] = {"name": name, "password": password}
        user_ids[email] = user_id
        print(f"已创建 {name}（{email}）")
    ACCOUNTS_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")

    groups = {
        r["name"]: r["id"]
        for r in store().query_read("SELECT id, name FROM user_group")
    }
    for email, name, group in USERS:
        if group not in groups:
            print(f"跳过 {name}：用户组 {group} 不存在，先运行 configure_platform.py content")
            continue
        store().query_write(
            "INSERT INTO user_group__member (group_id, user_id) VALUES (:g, :u) ON CONFLICT DO NOTHING",
            {"g": groups[group], "u": user_ids[email]},
        )
    print(f"账号与密码见 {ACCOUNTS_FILE.name}（不要提交）")


if __name__ == "__main__":
    main()
