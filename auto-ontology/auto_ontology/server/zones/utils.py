# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Zone constants, graph label helpers, and API payload formatting."""

from __future__ import annotations

from auto_ontology.catalog.constants import Edges, Labels

from auto_ontology.server.zones.constants import LABEL_ZONE
from auto_ontology.dal.zone_labels import format_zone  # noqa: F401 - re-export

REL_CONTAINS = Edges.CONTAINS

ZONE_DATA_LABELS = (
    Labels.DB,
    Labels.SCHEMA,
    Labels.TABLE,
)

_AUTO_ONTOLOGY_LABEL_TO_API_NAME: dict[str, str] = {
    Labels.DB: "db",
    Labels.SCHEMA: "schema",
    Labels.TABLE: "table",
    LABEL_ZONE: "zone",
}


def _resolve_api_name(auto_ontology_label: str) -> str:
    """Map a Auto Ontology graph label to its API-facing name."""
    return _AUTO_ONTOLOGY_LABEL_TO_API_NAME.get(
        auto_ontology_label, auto_ontology_label.lower()
    )
