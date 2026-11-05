# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Read identities forwarded by the trusted private Next.js gateway.

Lives at the top of ``auto_ontology.server`` rather than under ``chat``, where it started:
the header is a property of the gateway every router sits behind, and chat was
only the first feature to need a caller's name. Tags read it too, to record who
created and last renamed one. The caller's SSO token, forwarded the same way,
is read here for the same reason.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

INTERNAL_USER_HEADER = "x-auto-ontology-user-id"


def resolve_internal_user(request: Request, *, required: bool) -> str | None:
    """Return the Auto Ontology user id supplied by the trusted private gateway.

    Direct callers that do not use conversation persistence may omit these
    headers. FastAPI must not be publicly reachable because the header is not
    independently authenticated here.
    """

    user_id = (request.headers.get(INTERNAL_USER_HEADER) or "").strip()
    if user_id:
        return user_id

    if required:
        raise HTTPException(
            status_code=401, detail="Authenticated conversation required"
        )
    return None


def resolve_subject_token(request: Request) -> str | None:
    """Return the caller's SSO JWT when a connection authenticates as the user.

    The frontend forwards the browser user's SSO token (or a service caller's
    own bearer token) as ``Authorization: Bearer``. Fail closed: when any
    connection has "Authenticate as signed-in user" enabled, a request without a
    token is rejected rather than allowed to run under that connection's PAT.

    Read by every route that queries a source database on a caller's behalf:
    chat, and browsing object instances.
    """
    from auto_ontology.connectors.databricks_oauth import (
        any_connection_uses_sso_federation,
    )

    if not any_connection_uses_sso_federation():
        return None

    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "A connection is configured to authenticate as the signed-in "
                "user, but the request carried no SSO bearer token."
            ),
        )
    return token


__all__ = [
    "INTERNAL_USER_HEADER",
    "resolve_internal_user",
    "resolve_subject_token",
]
