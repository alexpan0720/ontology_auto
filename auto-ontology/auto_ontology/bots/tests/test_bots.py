# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from auto_ontology.bots import __main__ as service
from auto_ontology.bots import config, core, dingtalk, feishu

RESULT = {
    "type": "result",
    "answer": {
        "response": "统计每个品类的销售额。",
        "sql_code": "SELECT category, SUM(x) FROM t GROUP BY category",
        "sql_response_from_db": [
            json.dumps(
                [
                    {"category": "手机", "total": 10},
                    {"category": "耳机|蓝牙", "total": 3},
                ]
            )
        ],
        "provenance": {
            "tables": [{"id": "t1", "name": "orders", "status": "pending"}],
            "terms": [{"id": "x", "name": "订单", "status": "certified"}],
            "sql_attributes": [],
            "column_attributes": [],
        },
    },
}


class TestCore:
    def test_clean_question_strips_mentions_but_not_emails(self) -> None:
        assert (
            core.clean_question("@_user_1  哪个品类 卖得最好？")
            == "哪个品类 卖得最好？"
        )
        assert (
            core.clean_question("@问数助手 查一下 a@b.com 的订单", ["问数助手"])
            == "查一下 a@b.com 的订单"
        )

    def test_parse_sse_returns_the_final_event(self) -> None:
        lines = [
            'data: {"type": "step", "node": "x"}',
            "",
            f"data: {json.dumps(RESULT)}",
            'data: {"type": "charts", "content": "c"}',
            "data: [DONE]",
        ]
        assert core.parse_sse(lines) == RESULT

    def test_format_answer_has_text_table_sql_and_provenance(self) -> None:
        title, body = core.format_answer(RESULT)
        assert title == "问数结果"
        assert body.startswith("统计每个品类的销售额。")
        assert "| category | total |" in body
        assert "耳机\\|蓝牙" in body  # a pipe in a value cannot break the table
        assert "```sql\nSELECT category" in body
        assert "1 张表 · 1 个术语（已认证 1/2）；数据表：orders" in body

    def test_long_results_are_cut_and_counted(self) -> None:
        rows = [{"n": i} for i in range(core.MAX_ROWS + 5)]
        table = core.format_table(rows)
        assert table.count("\n| ") == core.MAX_ROWS + 1
        assert f"共 {core.MAX_ROWS + 5} 行" in table

    def test_errors_are_explained(self) -> None:
        title, body = core.format_answer(
            {"type": "error", "message": "你没有权限查看以下字段：c.phone"}
        )
        assert title == "查询失败" and "c.phone" in body

    def test_empty_question_gets_help(self) -> None:
        asker = core.Asker("feishu", "ou_1", None, "")
        assert (
            core.answer_question("", asker, asker_fn=lambda *a: pytest.fail("asked"))[0]
            == "使用说明"
        )

    def test_unmatched_sender_asks_as_platform_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(core, "find_user_by_email", lambda email: None)
        asker = core.make_asker("dingtalk", "staff9", "张三", lambda: "z@corp.com")
        assert asker.user_id is None and asker.identity == "dingtalk:staff9"

    def test_lookup_failures_never_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom() -> str:
            raise RuntimeError("no permission")

        monkeypatch.setattr(
            core, "find_user_by_email", lambda email: "u1" if email else None
        )
        asker = core.make_asker("feishu", "ou_1", "", boom)
        assert asker.user_id is None

    def test_ask_sends_identity_and_source(self) -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200, text=f"data: {json.dumps(RESULT)}\n\ndata: [DONE]\n\n"
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        event = core.ask("销售额", core.Asker("feishu", "ou_1", "u1", "张三"), client)
        assert event == RESULT
        assert seen["headers"]["x-auto-ontology-user-id"] == "u1"
        assert seen["headers"]["x-auto-ontology-source"] == "feishu"
        assert seen["body"] == {"question": "销售额"}

    def test_semantic_layer_missing_is_explained(self) -> None:
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(409, json={"detail": "Semantic layer missing"})
            )
        )
        event = core.ask("q", core.Asker("feishu", "ou", None, ""), client)
        assert "语义层" in event["message"]


def _feishu_event(
    message_id: str = "om_1",
    chat_type: str = "p2p",
    mentions: Any = None,
    text: str = "销售额",
) -> Any:
    return SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id=message_id,
                chat_id="oc_1",
                chat_type=chat_type,
                message_type="text",
                mentions=mentions,
                content=json.dumps({"text": text}, ensure_ascii=False),
            ),
            sender=SimpleNamespace(sender_id=SimpleNamespace(open_id="ou_1")),
        )
    )


class FakeFeishuBot(feishu.Bot):
    def __init__(self) -> None:
        super().__init__(
            client=None, answer=lambda q, asker, chat_id=None: ("问数结果", f"答：{q}")
        )
        self.replies: list[tuple[str, str, str]] = []
        self.handled: list[Any] = []

    def email(self, open_id: str) -> str | None:
        return "a@corp.com"

    def reply(self, message_id: str, msg_type: str, content: str) -> None:
        self.replies.append((message_id, msg_type, content))


class TestFeishu:
    def test_message_text_reads_text_and_post(self) -> None:
        assert feishu.message_text('{"text": "@_user_1 销售额"}') == "@_user_1 销售额"
        post = {
            "zh_cn": {
                "title": "",
                "content": [
                    [{"tag": "text", "text": "哪个"}, {"tag": "text", "text": "品类"}]
                ],
            }
        }
        assert feishu.message_text(json.dumps(post)) == "哪个 品类"

    def test_duplicates_and_unmentioned_group_messages_are_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bot = FakeFeishuBot()
        started: list[Any] = []
        monkeypatch.setattr(
            feishu.threading,
            "Thread",
            lambda target, args, daemon: SimpleNamespace(
                start=lambda: started.append(args)
            ),
        )
        bot.on_message(_feishu_event("om_1"))
        bot.on_message(_feishu_event("om_1"))
        bot.on_message(_feishu_event("om_2", chat_type="group", mentions=[]))
        assert len(started) == 1

    def test_handle_acknowledges_then_replies_with_a_card(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(core, "find_user_by_email", lambda email: "u1")
        bot = FakeFeishuBot()
        mention = SimpleNamespace(name="问数助手")
        bot.handle(
            _feishu_event(chat_type="group", mentions=[mention], text="@_user_1 销售额")
        )
        assert [r[1] for r in bot.replies] == ["text", "interactive"]
        card = json.loads(bot.replies[1][2])
        assert card["schema"] == "2.0"
        assert card["body"]["elements"][0]["content"] == "答：销售额"


class TestDingTalk:
    def test_handler_replies_and_acks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import dingtalk_stream

        monkeypatch.setattr(core, "find_user_by_email", lambda email: "u1")
        directory = SimpleNamespace(email=lambda staff_id: "z@corp.com")
        asked: list[Any] = []

        def answer(
            question: str, asker: core.Asker, chat_id: str | None = None
        ) -> tuple[str, str]:
            asked.append((question, asker.identity, chat_id))
            return "问数结果", "答案"

        handler = dingtalk.build_handler(directory, answer)
        sent: list[Any] = []
        handler.reply_text = lambda text, message: sent.append(("text", text))
        handler.reply_markdown = lambda title, text, message: sent.append(
            ("markdown", title, text)
        )
        callback = SimpleNamespace(
            data={
                "msgtype": "text",
                "text": {"content": " 哪个品类毛利最高？"},
                "senderStaffId": "staff1",
                "senderNick": "张三",
                "conversationType": "1",
                "sessionWebhook": "https://example.invalid/hook",
                "conversationId": "cid-1",
            }
        )
        code, _ = asyncio.run(handler.process(callback))
        assert code == dingtalk_stream.AckMessage.STATUS_OK
        assert asked == [("哪个品类毛利最高？", "u1", "cid-1")]
        assert sent == [("text", "正在查询，请稍候…"), ("markdown", "问数结果", "答案")]


class FakeProcess:
    instances: list["FakeProcess"] = []

    def __init__(self, target: Any, args: tuple, daemon: bool, name: str) -> None:
        self.args, self.alive, self.exitcode, self.terminated = args, False, None, False
        self.pid = 1000 + len(FakeProcess.instances)
        FakeProcess.instances.append(self)

    def start(self) -> None:
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.alive, self.terminated = False, True

    def join(self, timeout: float | None = None) -> None:
        pass


class TestSupervisor:
    @pytest.fixture
    def supervisor(self, monkeypatch: pytest.MonkeyPatch) -> service.Supervisor:
        FakeProcess.instances = []
        statuses: list[tuple] = []
        monkeypatch.setattr(config, "set_status", lambda *a: statuses.append(a))
        monkeypatch.setattr(config, "load", lambda platform: {})
        sup = service.Supervisor()
        sup._ctx = SimpleNamespace(Process=FakeProcess)
        sup.statuses = statuses  # type: ignore[attr-defined]
        return sup

    def test_starts_restarts_and_stops(self, supervisor: service.Supervisor) -> None:
        row = {"enabled": True, "app_id": "a", "app_secret": "s"}
        supervisor.tick({"feishu": row})
        assert [p.args for p in FakeProcess.instances] == [("feishu", "a", "s")]

        supervisor.tick({"feishu": row})  # unchanged: nothing new
        assert len(FakeProcess.instances) == 1

        supervisor.tick(
            {"feishu": {**row, "app_secret": "s2"}}
        )  # new secret: reconnect
        assert FakeProcess.instances[0].terminated
        assert FakeProcess.instances[1].args == ("feishu", "a", "s2")

        supervisor.tick({"feishu": {**row, "enabled": False, "status": "connected"}})
        assert FakeProcess.instances[1].terminated
        assert ("feishu", config.STATUS_STOPPED, "未启用") in supervisor.statuses  # type: ignore[attr-defined]

    def test_a_crashed_bot_is_retried_after_a_pause(
        self, supervisor: service.Supervisor, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        row = {"enabled": True, "app_id": "a", "app_secret": "s"}
        clock = [100.0]
        monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
        supervisor.tick({"dingtalk": row})
        FakeProcess.instances[0].alive = False
        FakeProcess.instances[0].exitcode = 1
        supervisor.tick({"dingtalk": row})
        assert len(FakeProcess.instances) == 1  # waiting out the retry pause
        assert supervisor.statuses[-1][1] == config.STATUS_ERROR  # type: ignore[attr-defined]
        clock[0] += service.RETRY_S + 1
        supervisor.tick({"dingtalk": row})
        assert len(FakeProcess.instances) == 2


def test_the_process_target_is_importable_by_a_spawned_child() -> None:
    """A spawned child re-imports its target by module name, never ``__main__``."""
    from auto_ontology.bots.serve import serve

    assert serve.__module__ == "auto_ontology.bots.serve"
    assert service.serve is serve


def _result(response: str, sql: str = "SELECT 1", resolved: str | None = None) -> dict:
    answer: dict[str, Any] = {"response": response, "sql_code": sql}
    if resolved:
        answer["resolved_question"] = resolved
    return {"type": "result", "answer": answer}


class TestFollowUps:
    def test_history_is_sent_and_built_up_per_thread(self) -> None:
        memory = core.ConversationMemory()
        sent: list[tuple[str, list]] = []
        replies = iter(
            [
                _result("各品类销售额如下", "SELECT category, SUM(x)"),
                _result("华东各品类销售额如下", resolved="华东各品类的销售额"),
            ]
        )

        def asker_fn(question: str, asker: core.Asker, history: list) -> dict:
            sent.append((question, history))
            return next(replies)

        alice = core.Asker("feishu", "ou_a", "u1", "Alice")
        core.answer_question(
            "各品类销售额", alice, chat_id="g1", asker_fn=asker_fn, memory=memory
        )
        title, body = core.answer_question(
            "那华东呢？", alice, chat_id="g1", asker_fn=asker_fn, memory=memory
        )
        assert sent[0][1] == []
        assert sent[1][1] == [
            {
                "question": "各品类销售额",
                "response": "各品类销售额如下",
                "sql_code": "SELECT category, SUM(x)",
            }
        ]
        assert body.startswith("> 理解为：华东各品类的销售额")
        # The next follow-up builds on the standalone reading.
        assert memory.history(core.thread_key(alice, "g1"))[-1]["question"] == (
            "华东各品类的销售额"
        )

    def test_threads_are_per_person_and_per_chat(self) -> None:
        memory = core.ConversationMemory()
        alice = core.Asker("feishu", "ou_a", "u1", "")
        bob = core.Asker("feishu", "ou_b", None, "")
        memory.remember(core.thread_key(alice, "g1"), "q", _result("a"))
        assert memory.history(core.thread_key(bob, "g1")) == []
        assert memory.history(core.thread_key(alice, "g2")) == []
        assert len(memory.history(core.thread_key(alice, "g1"))) == 1

    def test_failures_are_not_remembered_and_old_turns_drop_off(self) -> None:
        memory = core.ConversationMemory(turns=2)
        memory.remember("k", "bad", {"type": "error", "message": "x"})
        assert memory.history("k") == []
        for q in ("q1", "q2", "q3"):
            memory.remember("k", q, _result(q))
        assert [t["question"] for t in memory.history("k")] == ["q2", "q3"]

    def test_an_idle_thread_starts_over(self) -> None:
        now = [0.0]
        memory = core.ConversationMemory(ttl_s=60, clock=lambda: now[0])
        memory.remember("k", "q", _result("a"))
        now[0] = 61
        assert memory.history("k") == []

    def test_reset_word_clears_the_thread(self) -> None:
        memory = core.ConversationMemory()
        asker = core.Asker("dingtalk", "s1", "u1", "")
        memory.remember(core.thread_key(asker, "c"), "q", _result("a"))
        title, _ = core.answer_question(
            "新问题",
            asker,
            chat_id="c",
            asker_fn=lambda *a, **k: pytest.fail("asked"),
            memory=memory,
        )
        assert title == "已重新开始"
        assert memory.history(core.thread_key(asker, "c")) == []

    def test_ask_sends_history_only_when_there_is_some(self) -> None:
        bodies: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content))
            return httpx.Response(200, text=f"data: {json.dumps(RESULT)}\n\n")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        asker = core.Asker("feishu", "ou", "u1", "")
        core.ask("q", asker, client)
        core.ask("q2", asker, client, history=[{"question": "q", "response": "a"}])
        assert "history" not in bodies[0]
        assert bodies[1]["history"] == [{"question": "q", "response": "a"}]
