# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PostgreSQL-backed lookup of a user's role (Better Auth ``user`` table).

PostgreSQL is the single source of truth for whether a user is an ``admin``
or a ``viewer`` — the catalog only stores a single, role-agnostic
``User`` node (see ``auto_ontology.dal.users``).  Anything that needs to gate access
(e.g. "can this user manage zones?", "does this user see every zone?")
must go through :func:`get_user_role` / :func:`is_admin` instead of reading
a label or property off the graph node.
"""

from __future__ import annotations

import logging


from auto_ontology.dal.schema import GroupRole

# Lives in the DAL so data-access modules need not import the server layer;
# re-exported here for the callers (and tests) that patch it on this module.
from auto_ontology.dal.users import get_user_role  # noqa: F401

logger = logging.getLogger(__name__)


def is_admin(user_id: str) -> bool:
    """Return whether *user_id* currently has the ``admin`` role in Postgres."""
    return get_user_role(user_id) == GroupRole.ADMIN
