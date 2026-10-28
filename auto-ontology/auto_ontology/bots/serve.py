# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Entry point of one platform's bot process.

It lives outside ``__main__`` so a spawned child, which re-imports its target
by module name, can find it when the service runs as ``python -m``.
"""

from __future__ import annotations

import logging


def serve(platform: str, app_id: str, app_secret: str) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if platform == "dingtalk":
        from auto_ontology.bots.dingtalk import run
    else:
        from auto_ontology.bots.feishu import run
    run(app_id, app_secret)
