"""Settings endpoints with validation and key masking (PLAN 8.9)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.settings import pi_models, store

router = APIRouter()


@router.get("/api/settings")
async def get_settings(request: Request):
    return store.masked(store.load(request.app.state.data_dir))


@router.put("/api/settings")
async def put_settings(request: Request):
    body = await request.json()
    state = request.app.state
    backend = (body.get("asr") or {}).get("backend")
    if backend not in ("local", "cloud"):
        return JSONResponse({"code": "INVALID_ASR_BACKEND"}, status_code=422)
    stored = store.load(state.data_dir)
    incoming = store.restore_secrets(body, stored)
    if backend == "cloud" and not (incoming["asr"].get("dashscope_api_key") or "").strip():
        return JSONResponse({"code": "DASHSCOPE_KEY_REQUIRED"}, status_code=422)
    store.save(state.data_dir, incoming)
    if incoming["llm"]["provider"] == "custom":
        pi_models.apply_custom_provider(state.data_dir, incoming["llm"].get("custom"))
    return store.masked(store.load(state.data_dir))
