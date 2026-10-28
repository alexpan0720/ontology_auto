# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Start due subscriptions; runs in the bot service's polling loop.

Claiming a due row moves its ``next_run_at`` forward in the same transaction
(see :func:`auto_ontology.dal.subscriptions.claim_due`), so a slow or failed
run is never repeated by the next tick. The run itself happens in the API
server, through the same endpoint as "立即运行", so there is one code path.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from auto_ontology.dal import subscriptions as dal
from auto_ontology.subscriptions import schedule

logger = logging.getLogger(__name__)

#: A run queries a warehouse and posts to chat apps; give it time.
RUN_TIMEOUT_S = 600.0


def next_after(row: dict[str, Any]) -> datetime | None:
    """The slot after now; None (never due again) if the schedule is broken."""
    try:
        return schedule.next_run(
            row["schedule"],
            row["time_of_day"],
            row["weekday"],
            row["timezone"],
            datetime.now(timezone.utc),
        )
    except schedule.ScheduleError:
        logger.exception("Subscription %s has an invalid schedule", row["id"])
        return None


class Scheduler:
    def __init__(
        self,
        backend_url: str,
        *,
        workers: int = 2,
        post: Callable[..., Any] = httpx.post,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.post = post
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sub")

    def tick(self, now: datetime | None = None) -> list[str]:
        """Claim every due subscription and start its run; returns their ids."""
        claimed = dal.claim_due(now or datetime.now(timezone.utc), next_after)
        for subscription_id in claimed:
            self.pool.submit(self._run, subscription_id)
        return claimed

    def _run(self, subscription_id: str) -> None:
        try:
            response = self.post(
                f"{self.backend_url}/api/subscriptions/{subscription_id}/run",
                json={"trigger": "schedule"},
                timeout=RUN_TIMEOUT_S,
            )
            logger.info(
                "Subscription %s ran: HTTP %s", subscription_id, response.status_code
            )
        except Exception:  # noqa: BLE001 - one run failing must not stop the rest
            logger.exception("Subscription %s could not be started", subscription_id)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
