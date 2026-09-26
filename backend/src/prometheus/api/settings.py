"""Settings endpoints with validation and key masking (PLAN 8.9)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus import paths
from prometheus.llm import capability, pi_models
from prometheus.llm.one_shot import OneShotError, run_one_shot
from prometheus.settings import store

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
    protocol = ((body.get("llm") or {}).get("custom") or {}).get("protocol", "openai")
    if protocol not in pi_models.PROTOCOL_APIS:
        return JSONResponse({"code": "INVALID_PROTOCOL"}, status_code=422)
    stored = store.load(state.data_dir)
    incoming = store.restore_secrets(body, stored)
    if backend == "cloud" and not (incoming["asr"].get("dashscope_api_key") or "").strip():
        return JSONResponse({"code": "DASHSCOPE_KEY_REQUIRED"}, status_code=422)
    store.save(state.data_dir, incoming)
    if incoming["llm"]["provider"] == "custom":
        pi_models.apply_custom_provider(state.data_dir, incoming["llm"].get("custom"))
    return store.masked(store.load(state.data_dir))


@router.post("/api/settings/test-model")
def test_model(request: Request):
    """One-shot text call + capability query (PLAN 8.2/8.6/8.7)."""
    state = request.app.state
    found = state.get_runtime()
    llm = store.load(state.data_dir)["llm"]
    probe_dir = paths.pi_config_dir(state.data_dir)
    try:
        reply = run_one_shot(
            probe_dir, prompt="回复两个字：可用", provider=llm["provider"],
            model=llm["model"], api_key=llm.get("api_key") or "",
            thinking=llm.get("thinking") or "low",
            node_exe=str(found.node), pi_cli=str(found.pi_cli), agent_dir=probe_dir,
        )
    except OneShotError as exc:
        return JSONResponse({"ok": False, "detail": str(exc)[:200]}, status_code=200)
    images = capability.query_supports_images(found.node, found.pi_cli, state.data_dir, llm)
    return JSONResponse(
        {"ok": True, "detail": f"{reply[:60]} · 支持看图：{'是' if images else '否'}"},
        status_code=200,
    )
