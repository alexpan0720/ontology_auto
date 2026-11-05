# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""API routes for object types, link types, and browsing object instances."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auto_ontology.dal import objects as dal
from auto_ontology.dal import schema as s
from auto_ontology.objects import instances, service
from auto_ontology.server.identity import resolve_internal_user, resolve_subject_token

router = APIRouter()

Status = Literal["candidate", "active"]


def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _type_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="对象类型不存在")


def _user(request: Request) -> str | None:
    return resolve_internal_user(request, required=False)


# ---------------------------------------------------------------------------
# Object types
# ---------------------------------------------------------------------------


@router.get("/object-types")
def list_object_types(status: Status | None = None) -> dict[str, Any]:
    """Object types, optionally of one status, with the layer's totals."""
    rows = dal.list_object_types(status=status)
    return {"data": rows, "count": len(rows), "summary": dal.counts()}


@router.post("/object-types/generate")
def generate_object_types(request: Request) -> dict[str, Any]:
    """Propose object and link types from the catalog's keys and foreign keys."""
    return service.generate(_user(request))


class ObjectTypeCreate(BaseModel):
    table_id: str
    display_name: str | None = None
    #: Defaults to the table's key, or a column named like one.
    pk_column: str | None = None


@router.post("/object-types", status_code=201)
def create_object_type(body: ObjectTypeCreate, request: Request) -> dict[str, str]:
    """Define an object type over a table directly, already active."""
    columns = service.table_columns(body.table_id)
    if columns is None:
        raise _bad("数据表不存在")
    if body.pk_column and body.pk_column not in {c["name"] for c in columns}:
        raise _bad(f"字段不存在：{body.pk_column}")
    spec = service.new_type_spec(body.table_id, body.pk_column)
    if spec is None:
        raise _bad("这张表没有主键，请指定用作主键的字段")
    if body.display_name and body.display_name.strip():
        spec["display_name"] = body.display_name.strip()
    try:
        type_id = dal.create_object_type(
            {**spec, "status": s.OBJECT_ACTIVE}, created_by=_user(request)
        )
    except dal.ObjectTypeConflict as exc:
        raise _bad("这张表已经定义了对象类型") from exc
    return {"id": type_id}


class BulkAction(BaseModel):
    ids: list[str]
    action: Literal["accept", "delete"]


@router.post("/object-types/bulk")
def bulk_object_types(body: BulkAction, request: Request) -> dict[str, int]:
    """Confirm or delete many types at once.

    Confirming also confirms the candidate links between confirmed types.
    """
    if body.action == "accept":
        return service.accept(body.ids, _user(request))
    return {"types": dal.delete_object_types(body.ids), "links": 0}


@router.get("/object-types/{type_id}")
def get_object_type(type_id: str) -> dict[str, Any]:
    """A type with its properties and links."""
    described = service.describe(type_id)
    if described is None:
        raise _type_not_found()
    return described


class PropertyOverride(BaseModel):
    column_name: str
    display_name: str | None = None
    hidden: bool = False


class ObjectTypeUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    pk_column: str | None = None
    #: Empty clears it, so instances are called by their key.
    title_column: str | None = None
    status: Status | None = None
    #: Replaces every override when given.
    properties: list[PropertyOverride] | None = None


@router.patch("/object-types/{type_id}")
def update_object_type(
    type_id: str, body: ObjectTypeUpdate, request: Request
) -> dict[str, bool]:
    """Rename a type, pick its key or title, or rename and hide its properties."""
    current = dal.get_object_type(type_id)
    if current is None:
        raise _type_not_found()
    columns = {c["name"] for c in service.table_columns(current["table_id"]) or []}
    changes = body.model_dump(exclude_unset=True, exclude={"properties"})
    if "display_name" in changes:
        changes["display_name"] = (changes["display_name"] or "").strip()
        if not changes["display_name"]:
            raise _bad("请填写对象名称")
    if "pk_column" in changes and changes["pk_column"] not in columns:
        raise _bad("主键字段不存在")
    if "title_column" in changes:
        changes["title_column"] = changes["title_column"] or None
        if changes["title_column"] and changes["title_column"] not in columns:
            raise _bad("标题字段不存在")
    properties = None
    if body.properties is not None:
        unknown = [
            p.column_name for p in body.properties if p.column_name not in columns
        ]
        if unknown:
            raise _bad(f"字段不存在：{'、'.join(unknown)}")
        properties = [p.model_dump() for p in body.properties]
    dal.update_object_type(
        type_id, changes, properties=properties, modified_by=_user(request)
    )
    return {"ok": True}


@router.delete("/object-types/{type_id}")
def delete_object_type(type_id: str) -> dict[str, bool]:
    """Delete a type and every link touching it. The table is untouched."""
    if not dal.delete_object_types([type_id]):
        raise _type_not_found()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------


def _active_view(type_id: str, request: Request) -> tuple[Any, instances.Reader]:
    """An active type resolved for the caller, and the reader to query it with."""
    from auto_ontology.dal.governance import resolve_access

    user_id = _user(request)
    reader = instances.Reader(
        user_id=user_id,
        access=resolve_access(user_id),
        subject_token=resolve_subject_token(request),
    )
    view = instances.load_view(type_id, reader.access)
    if view is None or view.type["status"] != s.OBJECT_ACTIVE:
        raise _type_not_found()
    return view, reader


@router.get("/object-types/{type_id}/objects")
def list_objects(
    type_id: str,
    request: Request,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """One page of a type's instances, read under the caller's data policies."""
    view, reader = _active_view(type_id, request)
    try:
        page = instances.list_objects(
            view, reader, search=search, limit=limit, offset=offset
        )
    except instances.ObjectQueryError as exc:
        raise _bad(str(exc)) from exc
    labels = {p["column_name"]: p["label"] for p in view.properties}
    return {
        **page,
        "columns": [{"name": c, "label": labels.get(c, c)} for c in page["columns"]],
        "pk_column": view.pk,
        "title_column": view.title,
    }


@router.get("/object-types/{type_id}/object")
def get_object(type_id: str, key: str, request: Request) -> dict[str, Any]:
    """One instance by key, with the instances its links lead to."""
    view, reader = _active_view(type_id, request)
    try:
        found = instances.get_object(view, key, reader)
    except instances.ObjectQueryError as exc:
        raise _bad(str(exc)) from exc
    if found is None:
        raise HTTPException(status_code=404, detail="找不到这个对象，或没有查看权限")
    shown = set(found["values"])
    return {
        **found,
        "object_type": {
            "id": view.type["id"],
            "display_name": view.type["display_name"],
            "description": view.type["description"],
        },
        "properties": [
            {"name": p["column_name"], "label": p["label"]}
            for p in view.properties
            if p["column_name"] in shown
        ],
    }


# ---------------------------------------------------------------------------
# Link types
# ---------------------------------------------------------------------------


class LinkTypeCreate(BaseModel):
    object_type_id: str
    source_column: str
    target_object_type_id: str
    #: Defaults to the target type's key.
    target_column: str | None = None
    display_name: str | None = None
    reverse_display_name: str | None = None


@router.post("/link-types", status_code=201)
def create_link_type(body: LinkTypeCreate, request: Request) -> dict[str, str]:
    """Link two types through a column of the first, already active."""
    types = dal.get_object_types([body.object_type_id, body.target_object_type_id])
    source, target = (
        types.get(body.object_type_id),
        types.get(body.target_object_type_id),
    )
    if source is None or target is None:
        raise _type_not_found()
    target_column = body.target_column or target["pk_column"]
    if body.source_column not in {
        c["name"] for c in service.table_columns(source["table_id"]) or []
    }:
        raise _bad(f"字段不存在：{body.source_column}")
    if target_column not in {
        c["name"] for c in service.table_columns(target["table_id"]) or []
    }:
        raise _bad(f"字段不存在：{target_column}")
    ids = dal.create_link_types(
        [
            {
                "object_type_id": source["id"],
                "target_object_type_id": target["id"],
                "source_column": body.source_column,
                "target_column": target_column,
                "display_name": (body.display_name or "").strip()
                or target["display_name"],
                "reverse_display_name": (body.reverse_display_name or "").strip()
                or source["display_name"],
                "origin": s.LINK_MANUAL,
                "status": s.OBJECT_ACTIVE,
            }
        ],
        created_by=_user(request),
    )
    if not ids:
        raise _bad("这两个对象之间已经有经过该字段的关系")
    return {"id": ids[0]}


class LinkTypeUpdate(BaseModel):
    display_name: str | None = None
    reverse_display_name: str | None = None
    status: Status | None = None


@router.patch("/link-types/{link_id}")
def update_link_type(
    link_id: str, body: LinkTypeUpdate, request: Request
) -> dict[str, bool]:
    """Rename either direction of a link, or confirm it."""
    changes = body.model_dump(exclude_unset=True)
    for name in ("display_name", "reverse_display_name"):
        if name in changes:
            changes[name] = (changes[name] or "").strip()
            if not changes[name]:
                raise _bad("请填写关系名称")
    if not dal.update_link_type(link_id, changes, modified_by=_user(request)):
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"ok": True}


@router.delete("/link-types/{link_id}")
def delete_link_type(link_id: str) -> dict[str, bool]:
    """Delete a link type."""
    if not dal.delete_link_type(link_id):
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"ok": True}
