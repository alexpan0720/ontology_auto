# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Business objects as question context: which object a table is, and its links.

Users ask in the object layer's words — "客户", "下单客户", "订单明细" — while
the catalog speaks in table and column names. Attaching the confirmed object
and its links to each candidate table lets SQL generation read "下单客户" as
``orders.customer_id = customers.customer_id`` instead of guessing.

Only confirmed types and links are used. Annotation is best-effort: a failure
to read the object layer leaves the tables as they were rather than failing
the question.
"""

from __future__ import annotations

import logging
from typing import Any

from auto_ontology.dal import objects as dal

logger = logging.getLogger(__name__)

#: The key the annotation is stored under on a relevant-table dict.
BUSINESS_OBJECT = "business_object"


def annotate_business_objects(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """*tables* with :data:`BUSINESS_OBJECT` set on each that backs an object.

    Tables already annotated are not read again, so calling this after more
    tables joined the list only costs a read for the new ones.
    """
    ids = [str(t["id"]) for t in tables if t.get("id") and BUSINESS_OBJECT not in t]
    pending = set(ids)
    if not ids:
        return tables
    try:
        context = dal.fetch_object_context(ids)
    except Exception:  # noqa: BLE001 - context is optional; the question is not
        logger.exception("Failed to read business objects for question context")
        return tables
    return [
        {**t, BUSINESS_OBJECT: context.get(str(t["id"]))}
        if str(t.get("id") or "") in pending
        else t
        for t in tables
    ]
