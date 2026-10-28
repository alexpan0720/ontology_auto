# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Send a message to a DingTalk or Feishu group through its custom robot.

A custom robot is added to a group in the chat app itself and gives a webhook
URL, optionally with a signing secret (加签). Only the platforms' own webhook
hosts are accepted, so a stored channel can never be pointed elsewhere.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from auto_ontology.dal import schema as s

TIMEOUT_S = 15.0

WEBHOOK_PREFIXES = {
    s.BOT_DINGTALK: ("https://oapi.dingtalk.com/robot/send?access_token=",),
    s.BOT_FEISHU: (
        "https://open.feishu.cn/open-apis/bot/v2/hook/",
        "https://open.larksuite.com/open-apis/bot/v2/hook/",
    ),
}


class ChannelError(ValueError):
    """An invalid channel; the message is user-facing."""


@dataclass(frozen=True)
class Delivery:
    ok: bool
    detail: str


def validate(platform: str, webhook_url: str) -> None:
    prefixes = WEBHOOK_PREFIXES.get(platform)
    if prefixes is None:
        raise ChannelError("未知的平台")
    if not any(webhook_url.startswith(p) for p in prefixes):
        name = "钉钉" if platform == s.BOT_DINGTALK else "飞书"
        raise ChannelError(
            f"{name}群机器人的 Webhook 地址应以 {prefixes[0]} 开头，"
            "请在群设置 → 机器人 → 自定义机器人中复制"
        )


def dingtalk_signed_url(url: str, secret: str, now_ms: int) -> str:
    to_sign = f"{now_ms}\n{secret}".encode()
    digest = hmac.new(secret.encode(), to_sign, hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    return f"{url}&timestamp={now_ms}&sign={sign}"


def feishu_sign(secret: str, now_s: int) -> str:
    key = f"{now_s}\n{secret}".encode()
    return base64.b64encode(hmac.new(key, b"", hashlib.sha256).digest()).decode()


def _feishu_card(title: str, markdown: str, alert: bool) -> dict[str, Any]:
    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "red" if alert else "blue",
        },
        "body": {"elements": [{"tag": "markdown", "content": markdown}]},
    }


def send(
    channel: dict[str, Any],
    title: str,
    markdown: str,
    *,
    alert: bool = False,
    client: httpx.Client | None = None,
) -> Delivery:
    """Post one message; never raises — a failed delivery is reported."""
    platform, url, secret = (
        channel["platform"],
        channel["webhook_url"],
        channel.get("secret"),
    )
    try:
        validate(platform, url)
    except ChannelError as exc:
        return Delivery(False, str(exc))
    http = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        if platform == s.BOT_DINGTALK:
            if secret:
                url = dingtalk_signed_url(url, secret, int(time.time() * 1000))
            response = http.post(
                url,
                json={
                    "msgtype": "markdown",
                    "markdown": {"title": title, "text": f"### {title}\n\n{markdown}"},
                },
            )
            body = response.json()
            if body.get("errcode") == 0:
                return Delivery(True, "已送达")
            return Delivery(False, f"钉钉返回：{body.get('errmsg') or body}")
        payload: dict[str, Any] = {
            "msg_type": "interactive",
            "card": _feishu_card(title, markdown, alert),
        }
        if secret:
            now_s = int(time.time())
            payload.update(timestamp=str(now_s), sign=feishu_sign(secret, now_s))
        response = http.post(url, json=payload)
        body = response.json()
        if body.get("code", body.get("StatusCode")) == 0:
            return Delivery(True, "已送达")
        return Delivery(False, f"飞书返回：{body.get('msg') or body}")
    except (httpx.HTTPError, ValueError) as exc:
        return Delivery(False, f"发送失败：{exc}")
    finally:
        if client is None:
            http.close()
