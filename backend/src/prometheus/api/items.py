"""Item endpoints and the queue view (PLAN 8.2)."""

import asyncio
import sqlite3
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.ingest.links import LinkUnsupported, parse_url
from prometheus.library import items as items_store

router = APIRouter()

RETRYABLE = ("failed", "cancelled", "interrupted")


@router.post("/api/items", status_code=201)
async def create_item(request: Request):
    body = await request.json()
    try:
        source = parse_url(body.get("url") or "")
    except LinkUnsupported:
        return JSONResponse({"code": "URL_UNSUPPORTED"}, status_code=422)
    state = request.app.state
    try:
        item_id = items_store.create_item(
            state.data_dir, platform=source.platform, video_id=source.video_id,
            source_url=source.canonical_url, figures=1 if body.get("figures") else 0,
        )
    except sqlite3.IntegrityError:
        existing = items_store.find_by_video(state.data_dir, source.platform, source.video_id)
        return JSONResponse({"id": existing["id"]}, status_code=409)
    state.queue.enqueue(item_id)
    return {"id": item_id}


@router.get("/api/items")
async def list_items(
    request: Request, status: str | None = None, category_id: int | None = None,
):
    return items_store.list_items(
        request.app.state.data_dir, status=status, category_id=category_id,
    )


@router.get("/api/queue")
async def queue_view(request: Request):
    data_dir = request.app.state.data_dir
    active = [row for row in items_store.list_items(data_dir) if row["status"] != "done"]
    done = items_store.list_items(data_dir, status="done")
    return active + list(reversed(done[-20:]))


@router.get("/api/items/{item_id}")
async def get_item(request: Request, item_id: str):
    row = items_store.get_item(request.app.state.data_dir, item_id)
    if row is None:
        return JSONResponse({"code": "ITEM_NOT_FOUND"}, status_code=404)
    return row


@router.patch("/api/items/{item_id}")
async def patch_item(request: Request, item_id: str):
    body = await request.json()
    state = request.app.state
    if items_store.get_item(state.data_dir, item_id) is None:
        return JSONResponse({"code": "ITEM_NOT_FOUND"}, status_code=404)
    updates = {}
    if "category_id" in body:
        updates["category_id"] = body["category_id"]
    items_store.update_item(state.data_dir, item_id, **updates)
    return items_store.get_item(state.data_dir, item_id)


@router.delete("/api/items/{item_id}", status_code=204)
async def delete_item(request: Request, item_id: str):
    state = request.app.state
    row = items_store.get_item(state.data_dir, item_id)
    if row is None:
        return JSONResponse({"code": "ITEM_NOT_FOUND"}, status_code=404)
    if row["status"] in ("queued", "running"):
        # Deleting a live task: stop it first so no stage recreates the folder.
        state.queue.cancel(item_id)
        deadline = time.time() + 15
        while time.time() < deadline:
            current = items_store.get_item(state.data_dir, item_id)
            if current["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(0.05)
    items_store.delete_item(state.data_dir, item_id)
    return None


@router.post("/api/items/{item_id}/cancel")
async def cancel_item(request: Request, item_id: str):
    if not request.app.state.queue.cancel(item_id):
        return JSONResponse({"code": "NOT_CANCELLABLE"}, status_code=409)
    return {"cancelled": True}


@router.post("/api/items/{item_id}/retry")
async def retry_item(request: Request, item_id: str):
    return _requeue(request, item_id)


@router.post("/api/items/{item_id}/regenerate")
async def regenerate_item(request: Request, item_id: str):
    body = await request.json() if await request.body() else {}
    response = _requeue(request, item_id)
    if response.status_code == 200 and "figures" in body:
        items_store.update_item(
            request.app.state.data_dir, item_id, figures=1 if body["figures"] else 0,
        )
    return response


def _requeue(request: Request, item_id: str):
    state = request.app.state
    row = items_store.get_item(state.data_dir, item_id)
    if row is None:
        return JSONResponse({"code": "ITEM_NOT_FOUND"}, status_code=404)
    if row["status"] not in RETRYABLE:
        return JSONResponse({"code": "NOT_RETRYABLE"}, status_code=409)
    items_store.update_item(
        state.data_dir, item_id, status="queued", stage=None,
        error_code=None, error_message=None, finished_at=None,
    )
    state.queue.enqueue(item_id)
    return {"queued": True}
