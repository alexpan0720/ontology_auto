# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Bot service: keep one process per enabled platform, in step with its settings.

It also starts due metric subscriptions (see
:mod:`auto_ontology.subscriptions.scheduler`) on the same polling loop.

Each platform runs in its own process because neither SDK can be stopped
cleanly from outside its blocking loop: changing a platform's credentials, or
disabling it, terminates that process and starts a fresh one.
"""

from __future__ import annotations

import hashlib
import logging
import multiprocessing as mp
import time
from dataclasses import dataclass
from typing import Any

from auto_ontology.bots import config
from auto_ontology.bots.core import BACKEND_URL
from auto_ontology.bots.serve import serve
from auto_ontology.subscriptions.scheduler import Scheduler

logger = logging.getLogger("auto_ontology.bots")

POLL_S = 15.0
RETRY_S = 30.0


def _fingerprint(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{row.get('app_id')}\0{row.get('app_secret')}".encode()
    ).hexdigest()


@dataclass
class Running:
    process: mp.Process
    fingerprint: str


class Supervisor:
    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self.running: dict[str, Running] = {}
        self.retry_after: dict[str, float] = {}

    def _stop(self, platform: str) -> None:
        current = self.running.pop(platform, None)
        if current and current.process.is_alive():
            current.process.terminate()
            current.process.join(timeout=10)

    def tick(self, rows: dict[str, dict[str, Any]]) -> None:
        now = time.monotonic()
        for platform in config.PLATFORMS:
            row = rows.get(platform) or {}
            wanted = bool(
                row.get("enabled") and row.get("app_id") and row.get("app_secret")
            )
            current = self.running.get(platform)

            if not wanted:
                if current:
                    self._stop(platform)
                if row and row.get("status") != config.STATUS_STOPPED:
                    config.set_status(platform, config.STATUS_STOPPED, "未启用")
                continue

            fingerprint = _fingerprint(row)
            if current and current.fingerprint != fingerprint:
                logger.info("%s credentials changed; reconnecting", platform)
                self._stop(platform)
                current = None
            if current and not current.process.is_alive():
                code = current.process.exitcode
                self.running.pop(platform)
                current = None
                self.retry_after[platform] = now + RETRY_S
                latest = config.load(platform) or {}
                # A run that rejected its credentials already said why.
                if latest.get("status") != config.STATUS_ERROR or code not in (0, None):
                    config.set_status(
                        platform,
                        config.STATUS_ERROR,
                        f"连接中断（退出码 {code}），{int(RETRY_S)} 秒后重试",
                    )
            if current is None and now >= self.retry_after.get(platform, 0):
                process = self._ctx.Process(
                    target=serve,
                    args=(platform, row["app_id"], row["app_secret"]),
                    daemon=True,
                    name=f"bot-{platform}",
                )
                process.start()
                self.running[platform] = Running(process, fingerprint)
                logger.info("Started %s bot (pid %s)", platform, process.pid)

    def shutdown(self) -> None:
        for platform in list(self.running):
            self._stop(platform)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    supervisor = Supervisor()
    scheduler = Scheduler(BACKEND_URL)
    logger.info(
        "Bot and subscription service started; checking every %ss", int(POLL_S)
    )
    try:
        while True:
            try:
                supervisor.tick(config.load_all())
            except Exception:  # noqa: BLE001 - a store hiccup must not end the service
                logger.exception("Bot supervisor tick failed")
            try:
                scheduler.tick()
            except Exception:  # noqa: BLE001 - same: keep the loop alive
                logger.exception("Subscription scheduler tick failed")
            time.sleep(POLL_S)
    finally:
        supervisor.shutdown()
        scheduler.shutdown()


if __name__ == "__main__":
    main()
