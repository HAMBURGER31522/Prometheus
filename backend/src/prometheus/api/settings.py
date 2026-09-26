"""Settings endpoints with validation and key masking (PLAN 8.9)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus import paths
from prometheus.report.one_shot import OneShotError, run_one_shot
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


@router.post("/api/settings/test-model")
def test_model(request: Request):
    """One-shot text call + capability query (PLAN 8.2/8.6/8.7)."""
    from prometheus.tasks.stages import _node_exe, _pi_cli

    state = request.app.state
    settings = store.load(state.data_dir)
    llm = settings["llm"]
    api_key = llm.get("api_key") or ""
    probe_dir = paths.pi_config_dir(state.data_dir)
    try:
        reply = run_one_shot(
            probe_dir, prompt="回复两个字：可用", provider=llm["provider"],
            model=llm["model"], api_key=api_key, thinking=llm.get("thinking") or "low",
            node_exe=_node_exe(), pi_cli=_pi_cli(), agent_dir=probe_dir,
        )
    except OneShotError as exc:
        return JSONResponse({"ok": False, "detail": str(exc)[:200]}, status_code=200)
    import os

    from prometheus.settings.capability import model_supports_images

    images_command = [
        _node_exe(), _pi_cli(), "--offline", "--list-models",
    ]
    env = {**os.environ, "CUSTOM_API_KEY": api_key, "PI_API_KEY": api_key}
    import subprocess

    listing = subprocess.run(
        images_command, capture_output=True, env=env, timeout=60, check=False,
    )
    output = listing.stdout.decode("utf-8", "replace")
    images = model_supports_images(output, llm["model"])
    return JSONResponse(
        {"ok": True, "detail": f"{reply[:60]} · 支持看图：{'是' if images else '否'}"},
        status_code=200,
    )
