# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Instance routes: who the backend reads as, and with whose token."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auto_ontology.governance.enforce import AccessContext
from auto_ontology.objects import instances
from auto_ontology.server.identity import INTERNAL_USER_HEADER
from auto_ontology.server.objects import router as objects_router

VIEW = instances.TypeView(
    type={
        "id": "customer",
        "display_name": "客户",
        "description": None,
        "pk_column": "id",
        "title_column": None,
        "status": "active",
    },
    table={"name": "customers", "schema_name": "shop", "database_name": "db"},
    properties=[{"column_name": "id", "label": "编号", "hidden": False}],
)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(objects_router.router, prefix="/api")
    return TestClient(app)


def _listing(readers: list[instances.Reader]):
    def list_objects(view: Any, reader: instances.Reader, **_: Any) -> dict:
        readers.append(reader)
        return {"columns": ["id"], "objects": [], "has_more": False}

    return list_objects


def _patched(federated: bool, readers: list[instances.Reader]):
    access = AccessContext()
    return (
        patch(
            "auto_ontology.connectors.databricks_oauth.any_connection_uses_sso_federation",
            return_value=federated,
        ),
        patch("auto_ontology.dal.governance.resolve_access", return_value=access),
        patch.object(instances, "load_view", return_value=VIEW),
        patch.object(instances, "list_objects", _listing(readers)),
    )


def test_without_federation_the_shared_connection_is_used(client) -> None:
    readers: list[instances.Reader] = []
    a, b, c, d = _patched(False, readers)
    with a, b, c, d:
        resp = client.get(
            "/api/object-types/customer/objects",
            headers={INTERNAL_USER_HEADER: "u1", "Authorization": "Bearer ignored"},
        )
    assert resp.status_code == 200, resp.text
    assert readers[0].user_id == "u1"
    assert readers[0].subject_token is None


def test_a_federated_connection_reads_with_the_callers_token(client) -> None:
    readers: list[instances.Reader] = []
    a, b, c, d = _patched(True, readers)
    with a, b, c, d:
        resp = client.get(
            "/api/object-types/customer/objects",
            headers={INTERNAL_USER_HEADER: "u1", "Authorization": "Bearer sso-jwt"},
        )
    assert resp.status_code == 200, resp.text
    assert readers[0].subject_token == "sso-jwt"


def test_a_federated_connection_refuses_a_caller_without_a_token(client) -> None:
    readers: list[instances.Reader] = []
    a, b, c, d = _patched(True, readers)
    with a, b, c, d:
        resp = client.get(
            "/api/object-types/customer/object",
            params={"key": "1"},
            headers={INTERNAL_USER_HEADER: "u1"},
        )
    assert resp.status_code == 401
    assert readers == []
