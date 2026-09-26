"""Data directory endpoints (PLAN 8.1/8.2): first-run selection without restart."""

import json
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
    state = request.app.state
    if state.config_dir:
        state.config_dir.mkdir(parents=True, exist_ok=True)
        (state.config_dir / "app.json").write_text(
            json.dumps({"data_dir": str(state.data_dir)}), encoding="utf-8",
        )
    return {"data_dir": str(state.data_dir)}
