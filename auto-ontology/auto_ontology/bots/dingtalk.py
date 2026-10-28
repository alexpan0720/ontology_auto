# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DingTalk bot over Stream mode: no public callback URL is needed.

DingTalk delivers a group message to the bot only when the bot is @mentioned,
and every message in a one-to-one chat, so no mention check is needed here.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

import httpx

from auto_ontology.bots import config
from auto_ontology.bots.core import Asker, answer_question, clean_question, make_asker

logger = logging.getLogger(__name__)

PLATFORM = "dingtalk"
EMAIL_CACHE_S = 3600.0


class EmailDirectory:
    """A staff member's email from the DingTalk directory, cached for an hour.

    Needs the app's "通讯录个人信息读权限" (read contact information);
    without it the lookup returns nothing and the sender asks with no account.
    """

    def __init__(self, app_key: str, app_secret: str) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._token: tuple[str, float] | None = None
        self._emails: dict[str, tuple[str | None, float]] = {}

    def _access_token(self) -> str:
        if self._token and self._token[1] > time.monotonic():
            return self._token[0]
        data = httpx.get(
            "https://oapi.dingtalk.com/gettoken",
            params={"appkey": self._app_key, "appsecret": self._app_secret},
            timeout=10,
        ).json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"gettoken failed: {data}")
        self._token = (
            data["access_token"],
            time.monotonic() + int(data.get("expires_in", 7200)) - 300,
        )
        return self._token[0]

    def email(self, staff_id: str | None) -> str | None:
        if not staff_id:
            return None
        cached = self._emails.get(staff_id)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        data = httpx.post(
            "https://oapi.dingtalk.com/topapi/v2/user/get",
            params={"access_token": self._access_token()},
            json={"userid": staff_id},
            timeout=10,
        ).json()
        result = data.get("result") or {}
        email = result.get("org_email") or result.get("email") or None
        if data.get("errcode") not in (0, None):
            logger.warning("DingTalk user lookup failed: %s", data.get("errmsg"))
        self._emails[staff_id] = (email, time.monotonic() + EMAIL_CACHE_S)
        return email


def build_handler(
    directory: EmailDirectory, answer: Callable[..., tuple[str, str]] = answer_question
):
    """The Stream-mode chatbot handler, built lazily so the SDK import stays local."""
    import dingtalk_stream

    class Handler(dingtalk_stream.ChatbotHandler):
        async def process(self, callback: Any):  # type: ignore[override]
            message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            text = (
                message.text.content if getattr(message, "text", None) else ""
            ) or ""
            question = clean_question(text)
            asker: Asker = await asyncio.to_thread(
                make_asker,
                PLATFORM,
                message.sender_staff_id or message.sender_id or "",
                message.sender_nick or "",
                lambda: directory.email(message.sender_staff_id),
            )
            if question:
                self.reply_text("正在查询，请稍候…", message)
            title, body = await asyncio.to_thread(answer, question, asker)
            self.reply_markdown(title, body, message)
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    return Handler()


def run(app_key: str, app_secret: str) -> None:
    """Connect and serve until the process is stopped."""
    import dingtalk_stream

    problem = config.verify(PLATFORM, app_key, app_secret)
    if problem:
        config.set_status(PLATFORM, config.STATUS_ERROR, problem)
        return
    client = dingtalk_stream.DingTalkStreamClient(
        dingtalk_stream.Credential(app_key, app_secret)
    )
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC,
        build_handler(EmailDirectory(app_key, app_secret)),
    )
    config.set_status(PLATFORM, config.STATUS_CONNECTED, "已通过 Stream 模式连接钉钉")
    client.start_forever()
