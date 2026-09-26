"""Category endpoints (PLAN 8.2)."""

import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.library import categories as categories_store

router = APIRouter()


@router.get("/api/categories")
async def list_categories(request: Request):
    return categories_store.list_categories(request.app.state.data_dir)


@router.patch("/api/categories/{category_id}")
async def rename_category(request: Request, category_id: int):
    body = await request.json()
    try:
        categories_store.rename_category(request.app.state.data_dir, category_id, body["name"])
    except sqlite3.IntegrityError:
        return JSONResponse({"code": "CATEGORY_NAME_TAKEN"}, status_code=409)
    return {"renamed": True}


@router.delete("/api/categories/{category_id}", status_code=204)
async def delete_category(request: Request, category_id: int):
    if categories_store.item_count(request.app.state.data_dir, category_id) > 0:
        return JSONResponse({"code": "CATEGORY_NOT_EMPTY"}, status_code=409)
    categories_store.delete_category(request.app.state.data_dir, category_id)
    return None


@router.post("/api/categories/{category_id}/merge")
async def merge_category(request: Request, category_id: int):
    body = await request.json()
    categories_store.merge_category(request.app.state.data_dir, category_id, body["into_id"])
    return {"merged": True}
