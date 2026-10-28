# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import base64
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from auto_ontology.dal import schema as s
from auto_ontology.subscriptions import alerts, push, schedule, scheduler, service

UTC = timezone.utc


class TestSchedule:
    # 2026-10-28 is a Wednesday; 09:00 Shanghai is 01:00 UTC.
    WED_0800_SH = datetime(2026, 10, 28, 0, 0, tzinfo=UTC)

    def test_daily_later_today_then_tomorrow(self) -> None:
        nxt = schedule.next_run(
            "daily", "09:00", None, "Asia/Shanghai", self.WED_0800_SH
        )
        assert nxt == datetime(2026, 10, 28, 1, 0, tzinfo=UTC)
        again = schedule.next_run("daily", "09:00", None, "Asia/Shanghai", nxt)
        assert again == datetime(2026, 10, 29, 1, 0, tzinfo=UTC)

    def test_workdays_skip_the_weekend(self) -> None:
        friday_after = datetime(2026, 10, 30, 2, 0, tzinfo=UTC)
        nxt = schedule.next_run(
            "workdays", "09:00", None, "Asia/Shanghai", friday_after
        )
        assert nxt == datetime(2026, 11, 2, 1, 0, tzinfo=UTC)  # Monday

    def test_weekly_on_the_chosen_day(self) -> None:
        nxt = schedule.next_run("weekly", "09:00", 1, "Asia/Shanghai", self.WED_0800_SH)
        assert nxt == datetime(2026, 11, 2, 1, 0, tzinfo=UTC)

    def test_hourly_uses_the_minute(self) -> None:
        at = datetime(2026, 10, 28, 3, 20, tzinfo=UTC)
        assert schedule.next_run("hourly", "00:15", None, "Asia/Shanghai", at) == (
            datetime(2026, 10, 28, 4, 15, tzinfo=UTC)
        )

    @pytest.mark.parametrize(
        "args, message",
        [
            (("monthly", "09:00", None, "Asia/Shanghai"), "频率"),
            (("daily", "9:00", None, "Asia/Shanghai"), "HH:MM"),
            (("weekly", "09:00", None, "Asia/Shanghai"), "星期"),
            (("daily", "09:00", None, "Mars/Base"), "时区"),
        ],
    )
    def test_invalid_schedules_are_explained(self, args: tuple, message: str) -> None:
        with pytest.raises(schedule.ScheduleError, match=message):
            schedule.validate(*args)

    def test_describe(self) -> None:
        assert schedule.describe("weekly", "09:30", 1) == "每周一 09:30"
        assert schedule.describe("workdays", "08:00", None) == "工作日 08:00"


ROWS = [
    {"channel": "App", "orders": 120},
    {"channel": "小程序", "orders": 80},
    {"channel": "门店", "orders": "35"},
]


class TestAlerts:
    def test_threshold_lists_the_rows_that_cross(self) -> None:
        result = alerts.evaluate(
            ROWS, alert_type="threshold", column=None, op="<", value=50, previous=None
        )
        assert result.triggered and result.value_column == "orders"
        assert result.lines == ["门店：35（低于 50）"]

    def test_change_against_the_previous_run(self) -> None:
        previous = [
            {"channel": "App", "orders": 100},
            {"channel": "小程序", "orders": 100},
        ]
        result = alerts.evaluate(
            ROWS,
            alert_type="change",
            column="ORDERS",
            op="down",
            value=10,
            previous=previous,
        )
        assert result.lines == ["小程序：100 → 80（-20.0%）"]
        up = alerts.evaluate(
            ROWS,
            alert_type="change",
            column=None,
            op="any",
            value=15,
            previous=previous,
        )
        assert len(up.lines) == 2

    def test_first_change_run_has_no_baseline(self) -> None:
        result = alerts.evaluate(
            ROWS, alert_type="change", column=None, op="up", value=5, previous=None
        )
        assert not result.triggered and "首次运行" in (result.note or "")

    def test_single_number_is_labelled_by_its_column(self) -> None:
        result = alerts.evaluate(
            [{"gmv": 1234.5}],
            alert_type="threshold",
            column=None,
            op=">",
            value=1000,
            previous=None,
        )
        assert result.lines == ["gmv：1,234.50（高于 1,000）"]

    def test_no_numeric_column(self) -> None:
        result = alerts.evaluate(
            [{"name": "a"}],
            alert_type="threshold",
            column=None,
            op=">",
            value=1,
            previous=None,
        )
        assert not result.triggered and result.note

    @pytest.mark.parametrize(
        "args",
        [
            ("threshold", "!=", 1.0),
            ("change", "up", None),
            ("change", "up", -5.0),
            ("x", None, None),
        ],
    )
    def test_invalid_rules(self, args: tuple) -> None:
        with pytest.raises(alerts.AlertRuleError):
            alerts.validate(*args)

    def test_describe(self) -> None:
        assert (
            alerts.describe("change", "orders", "down", 20) == "orders 较上次下降 ≥ 20%"
        )


class TestPush:
    def test_only_platform_webhooks_are_accepted(self) -> None:
        with pytest.raises(push.ChannelError, match="oapi.dingtalk.com"):
            push.validate("dingtalk", "https://evil.example/robot/send?access_token=x")
        push.validate("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/abc")

    def test_dingtalk_signature(self) -> None:
        url = push.dingtalk_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=t", "SEC", 1700000000000
        )
        sign = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["sign"][0]
        expected = base64.b64encode(
            hmac.new(b"SEC", b"1700000000000\nSEC", hashlib.sha256).digest()
        ).decode()
        assert sign == expected and "timestamp=1700000000000" in url

    def test_feishu_signature(self) -> None:
        expected = base64.b64encode(
            hmac.new(b"1700000000\nSEC", b"", hashlib.sha256).digest()
        ).decode()
        assert push.feishu_sign("SEC", 1700000000) == expected

    def test_send_reports_platform_errors(self) -> None:
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            if "dingtalk" in str(request.url):
                return httpx.Response(
                    200, json={"errcode": 310000, "errmsg": "sign not match"}
                )
            return httpx.Response(200, json={"code": 0, "msg": "success"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        bad = push.send(
            {
                "platform": "dingtalk",
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=t",
                "secret": "s",
            },
            "标题",
            "正文",
            client=client,
        )
        assert not bad.ok and "sign not match" in bad.detail
        good = push.send(
            {
                "platform": "feishu",
                "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/x",
                "secret": "s",
            },
            "标题",
            "正文",
            alert=True,
            client=client,
        )
        assert good.ok
        card = seen[1]
        assert card["msg_type"] == "interactive" and card["sign"] and card["timestamp"]
        assert card["card"]["header"]["template"] == "red"

    def test_send_never_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        result = push.send(
            {
                "platform": "feishu",
                "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/x",
            },
            "t",
            "b",
            client=client,
        )
        assert not result.ok and "发送失败" in result.detail


def test_read_only_sql() -> None:
    service.check_read_only("SELECT 1", "postgres")
    service.check_read_only("WITH a AS (SELECT 1) SELECT * FROM a", "databricks")
    for sql in ("DELETE FROM t", "SELECT 1; DROP TABLE t", "UPDATE t SET a = 1"):
        with pytest.raises(service.RunError):
            service.check_read_only(sql, "postgres")


SUB = {
    "id": "sub1",
    "name": "各渠道订单",
    "sql": "SELECT channel, orders FROM t",
    "database_name": "workspace",
    "run_as_user_id": None,
    "schedule": "daily",
    "time_of_day": "09:00",
    "weekday": None,
    "timezone": "Asia/Shanghai",
    "channel_ids": ["c1", "c2"],
    "push_mode": "always",
    "alert_type": "threshold",
    "alert_column": "orders",
    "alert_op": "<",
    "alert_value": 50.0,
}


class FakeDal(SimpleNamespace):
    pass


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    recorded: list[dict[str, Any]] = []
    sub = dict(SUB)
    monkeypatch.setattr(
        service.dal, "get_subscription", lambda i: sub if i == "sub1" else None
    )
    monkeypatch.setattr(service.dal, "previous_rows", lambda i: None)
    monkeypatch.setattr(
        service.dal,
        "get_channels",
        lambda ids: [
            {"id": i, "name": f"群{i}", "platform": "feishu", "webhook_url": "u"}
            for i in ids
        ],
    )
    monkeypatch.setattr(
        service.dal, "record_run", lambda **kw: recorded.append(kw) or kw
    )
    recorded.append({"sub": sub})  # index 0 lets a test edit the subscription
    return recorded


def _query(rows: list[dict[str, Any]]) -> Any:
    return lambda *a: service.QueryResult(
        rows=rows, columns=list(rows[0]) if rows else []
    )


class TestExecute:
    def test_sends_with_the_alert_and_records(self, runs: list) -> None:
        sent: list[tuple] = []
        run = service.execute(
            "sub1",
            trigger="manual",
            query=_query(ROWS),
            sender=lambda ch, title, body, alert: (
                sent.append((ch["id"], title, body, alert))
                or push.Delivery(True, "已送达")
            ),
        )
        assert run["status"] == s.RUN_SENT and run["alerted"]
        assert run["summary"] == "触发预警，已推送到 2 个群"
        assert [x[0] for x in sent] == ["c1", "c2"]
        title, body = sent[0][1], sent[0][2]
        assert title == "⚠️ 预警：各渠道订单"
        assert "门店：35（低于 50）" in body and "channel：App｜orders：120" in body
        assert "普通用户（无用户组）" in body

    def test_alert_only_stays_quiet(self, runs: list) -> None:
        runs[0]["sub"].update(push_mode="on_alert", alert_op=">", alert_value=1000.0)
        run = service.execute(
            "sub1",
            trigger="schedule",
            query=_query(ROWS),
            sender=lambda *a, **k: pytest.fail("should not send"),
        )
        assert run["status"] == s.RUN_QUIET and run["deliveries"] == []

    def test_a_failed_query_is_recorded(self, runs: list) -> None:
        def boom(*a: Any) -> Any:
            raise service.RunError("你没有权限查看以下字段：customers.phone")

        run = service.execute("sub1", trigger="schedule", query=boom)
        assert run["status"] == s.RUN_FAILED and "customers.phone" in run["summary"]

    def test_partial_delivery_failure_is_named(self, runs: list) -> None:
        run = service.execute(
            "sub1",
            trigger="manual",
            query=_query(ROWS),
            sender=lambda ch, *a, **k: push.Delivery(ch["id"] == "c1", "关键词不匹配"),
        )
        assert run["status"] == s.RUN_SENT and "群c2：关键词不匹配" in run["summary"]


def test_scheduler_claims_and_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[str] = []
    monkeypatch.setattr(scheduler.dal, "claim_due", lambda now, next_after: ["a", "b"])
    sched = scheduler.Scheduler(
        "http://backend:3001/",
        post=lambda url, **kw: posted.append(url) or SimpleNamespace(status_code=200),
    )
    assert sched.tick() == ["a", "b"]
    sched.pool.shutdown(wait=True)
    assert sorted(posted) == [
        "http://backend:3001/api/subscriptions/a/run",
        "http://backend:3001/api/subscriptions/b/run",
    ]


def test_a_broken_schedule_is_never_due_again() -> None:
    row = {
        "id": "x",
        "schedule": "weekly",
        "time_of_day": "09:00",
        "weekday": None,
        "timezone": "Asia/Shanghai",
    }
    assert scheduler.next_after(row) is None
