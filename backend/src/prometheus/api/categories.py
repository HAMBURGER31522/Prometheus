"""Category endpoints (PLAN 8.2)."""

import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.library import categories as categories_store
from prometheus.library import index, publish

router = APIRouter()


@router.get("/api/categories")
async def list_categories(request: Request):
    return categories_store.list_categories(request.app.state.data_dir)


@router.post("/api/categories", status_code=201)
async def create_category(request: Request):
    """「+」 in the category column (PLAN 15.4.10)."""
    name = str((await request.json()).get("name") or "").strip()
    if not name:
        return JSONResponse({"code": "CATEGORY_NAME_EMPTY"}, status_code=422)
    try:
        category_id = categories_store.create_category(request.app.state.data_dir, name)
    except sqlite3.IntegrityError:
        return JSONResponse({"code": "CATEGORY_NAME_TAKEN"}, status_code=409)
    index.rebuild(request.app.state.data_dir)
    return {"id": category_id, "name": name}


@router.patch("/api/categories/{category_id}")
async def rename_category(request: Request, category_id: int):
    body = await request.json()
    try:
        publish.rename_category(request.app.state.data_dir, category_id, body["name"])
    except sqlite3.IntegrityError:
        return JSONResponse({"code": "CATEGORY_NAME_TAKEN"}, status_code=409)
    return {"renamed": True}


@router.delete("/api/categories/{category_id}", status_code=204)
async def delete_category(request: Request, category_id: int, move_items: int = 0):
    """With ?move_items=1 a non-empty category hands its items to 未分类 first (PLAN 15.4.10)."""
    data_dir = request.app.state.data_dir
    if categories_store.item_count(data_dir, category_id) > 0:
        if not move_items:
            return JSONResponse({"code": "CATEGORY_NOT_EMPTY"}, status_code=409)
        publish.merge_categories(data_dir, category_id, categories_store.ensure_category(data_dir, "未分类"))
        return None
    publish.delete_category(data_dir, category_id)
    return None


@router.post("/api/categories/{category_id}/merge")
async def merge_category(request: Request, category_id: int):
    body = await request.json()
    publish.merge_categories(request.app.state.data_dir, category_id, body["into_id"])
    return {"merged": True}
