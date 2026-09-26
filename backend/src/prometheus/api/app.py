"""Data directory endpoints (PLAN 8.1/8.2): first-run selection without restart."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/app/data-dir")
async def get_data_dir(request: Request) -> dict:
    data_dir = request.app.state.data_dir
    return {"data_dir": str(data_dir) if data_dir else None}


@router.put("/api/app/data-dir")
async def set_data_dir(request: Request):
    body = await request.json()
    raw = body.get("data_dir")
    if not raw:
        return JSONResponse({"code": "DATA_DIR_REQUIRED"}, status_code=422)
    request.app.state.initialize(Path(raw))
    return {"data_dir": str(request.app.state.data_dir)}
