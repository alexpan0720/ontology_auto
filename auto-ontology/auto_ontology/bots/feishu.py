# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Feishu (Lark) bot over a long connection: no public callback URL is needed.

Feishu expects an event to be acknowledged within seconds, so the handler only
queues the work; the answer is sent as a reply from a worker thread. Events can
be delivered more than once, hence the message-id de-duplication.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from typing import Any, Callable

from auto_ontology.bots import config
from auto_ontology.bots.core import answer_question, clean_question, make_asker

logger = logging.getLogger(__name__)

PLATFORM = "feishu"


class SeenMessages:
    """The last few thousand message ids, to drop redelivered events."""

    def __init__(self, size: int = 2000) -> None:
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def first_time(self, message_id: str) -> bool:
        with self._lock:
            if message_id in self._ids:
                return False
            self._ids[message_id] = None
            if len(self._ids) > self._size:
                self._ids.popitem(last=False)
            return True


def message_text(content: str) -> str:
    """The plain text of a ``text`` or ``post`` message's JSON content."""
    try:
        data = json.loads(content or "{}")
    except ValueError:
        return ""
    if "text" in data:
        return str(data["text"])
    # Rich text ("post"): concatenate its text runs.
    body = data.get("content") or next(
        (v.get("content") for v in data.values() if isinstance(v, dict)), []
    )
    runs = [
        run.get("text", "")
        for line in body or []
        for run in line or []
        if isinstance(run, dict) and run.get("tag") in ("text", "a")
    ]
    return " ".join(runs)


def card(title: str, markdown: str) -> str:
    """An interactive card (schema 2.0) whose markdown supports tables and code."""
    return json.dumps(
        {
            "schema": "2.0",
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "body": {"elements": [{"tag": "markdown", "content": markdown}]},
        },
        ensure_ascii=False,
    )


class Bot:
    """Handles ``im.message.receive_v1`` events for one app."""

    def __init__(
        self,
        client: Any,
        answer: Callable[..., tuple[str, str]] = answer_question,
    ) -> None:
        self.client = client
        self.answer = answer
        self.seen = SeenMessages()

    # -- Feishu API calls, kept small so tests can replace them --------------

    def email(self, open_id: str) -> str | None:
        from lark_oapi.api.contact.v3 import GetUserRequest

        response = self.client.contact.v3.user.get(
            GetUserRequest.builder().user_id(open_id).user_id_type("open_id").build()
        )
        if not response.success():
            logger.warning(
                "Feishu user lookup failed: %s %s", response.code, response.msg
            )
            return None
        user = response.data.user
        return getattr(user, "enterprise_email", None) or getattr(user, "email", None)

    def reply(self, message_id: str, msg_type: str, content: str) -> None:
        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        response = self.client.im.v1.message.reply(
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type(msg_type)
                .build()
            )
            .build()
        )
        if not response.success():
            logger.warning("Feishu reply failed: %s %s", response.code, response.msg)

    # -- Event handling --------------------------------------------------------

    def on_message(self, data: Any) -> None:
        """The SDK callback: accept fast, answer on a thread."""
        event = data.event
        message = event.message
        if not self.seen.first_time(message.message_id):
            return
        if message.chat_type == "group" and not (message.mentions or []):
            return  # only answer group messages that @mention the bot
        if message.message_type not in ("text", "post"):
            self.reply(
                message.message_id,
                "text",
                json.dumps({"text": "目前只支持文字提问。"}, ensure_ascii=False),
            )
            return
        threading.Thread(target=self.handle, args=(data,), daemon=True).start()

    def handle(self, data: Any) -> None:
        event = data.event
        message = event.message
        mention_names = [
            m.name for m in message.mentions or [] if getattr(m, "name", None)
        ]
        question = clean_question(message_text(message.content), mention_names)
        open_id = event.sender.sender_id.open_id
        asker = make_asker(PLATFORM, open_id, "", lambda: self.email(open_id))
        try:
            if question:
                self.reply(
                    message.message_id,
                    "text",
                    json.dumps({"text": "正在查询，请稍候…"}, ensure_ascii=False),
                )
            title, body = self.answer(question, asker)
            self.reply(message.message_id, "interactive", card(title, body))
        except Exception:  # noqa: BLE001 - one failed reply must not stop the bot
            logger.exception("Feishu question failed")


def run(app_id: str, app_secret: str) -> None:
    """Connect and serve until the process is stopped."""
    import lark_oapi as lark

    problem = config.verify(PLATFORM, app_id, app_secret)
    if problem:
        config.set_status(PLATFORM, config.STATUS_ERROR, problem)
        return
    api_client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
    bot = Bot(api_client)
    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(bot.on_message)
        .build()
    )
    config.set_status(PLATFORM, config.STATUS_CONNECTED, "已通过长连接连接飞书")
    lark.ws.Client(app_id, app_secret, event_handler=handler).start()
