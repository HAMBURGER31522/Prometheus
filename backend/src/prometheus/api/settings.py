"""Settings endpoints with validation and key masking (PLAN 8.9, 15.4.10)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus import paths
from prometheus.agents import rules, runs
from prometheus.llm import capability, catalogue_update, model_list, pi_models
from prometheus.llm.one_shot import OneShotError, run_one_shot
from prometheus.runtime import RuntimeConfigError
from prometheus.settings import store

router = APIRouter()


def _pi_cli(state):
    """The bundled Pi's cli.js, whose pi-ai catalogue knows the models' parameters."""
    try:
        return state.get_runtime().pi_cli
    except RuntimeConfigError:
        return None


@router.get("/api/settings")
async def get_settings(request: Request):
    return store.masked(store.load(request.app.state.data_dir))


@router.put("/api/settings")
async def put_settings(request: Request):
    body = await request.json()
    state = request.app.state
    backend = (body.get("asr") or {}).get("backend")
    if backend not in ("local", "cloud", "custom"):
        return JSONResponse({"code": "INVALID_ASR_BACKEND"}, status_code=422)
    if (body.get("report") or {}).get("depth", "full") not in store.REPORT_DEPTHS:
        return JSONResponse({"code": "INVALID_REPORT_DEPTH"}, status_code=422)
    if not isinstance((body.get("report") or {}).get("review", True), bool):
        return JSONResponse({"code": "INVALID_REPORT_REVIEW"}, status_code=422)
    protocols = [((body.get("llm") or {}).get("custom") or {}).get("protocol", "openai")]
    protocols += [p.get("protocol", "openai") for p in (body.get("llm_profiles") or {}).get("items", [])]
    if any(protocol not in pi_models.PROTOCOL_APIS for protocol in protocols):
        return JSONResponse({"code": "INVALID_PROTOCOL"}, status_code=422)
    for profile in (body.get("llm_profiles") or {}).get("items", []):
        if code := rules.problem(profile):  # the Agent and how it connects (PLAN 15.4.13)
            return JSONResponse({"code": code, "profile_id": profile.get("id")}, status_code=422)
    stored = store.load(state.data_dir)
    store.save(state.data_dir, store.restore_secrets(body, stored))
    saved = store.load(state.data_dir)
    # the custom provider's models.json entry, and Pi's compaction reserve for any provider (PLAN 15.4.14 I)
    pi_models.refresh_custom_provider(state.data_dir, pi_cli=_pi_cli(state))
    return store.masked(saved)


@router.post("/api/settings/reveal-key")
def reveal_key(request: Request, body: dict):
    """「显示 API Key」 (PLAN 15.4.10, user 2026-09-28): the full key, only when the eye asks for it."""
    settings = store.load(request.app.state.data_dir)
    if body.get("target") == "asr":
        return {"api_key": (settings["asr"].get("custom") or {}).get("api_key", "")}
    for item in settings["llm_profiles"]["items"]:
        if item["id"] == body.get("profile_id"):
            return {"api_key": item.get("api_key", "")}
    return JSONResponse({"code": "PROFILE_NOT_FOUND"}, status_code=404)


@router.post("/api/settings/models")
def list_models(request: Request, body: dict):
    """「获取模型列表」 for one profile (PLAN 15.4.8): only ever on the user's click."""
    state = request.app.state
    profile = dict(body.get("profile") or {})
    if profile.get("agent") == "codex" and profile.get("access") == "login":  # the account's list (15.4.13)
        return {"models": [model["id"] for model in state.agents.codex_models()]}
    profile["api_key"] = store.stored_key(state.data_dir, profile)
    proxy = store.load(state.data_dir)["network"].get("proxy", "")

    def pi_listing() -> str:
        found = state.get_runtime()
        llm = {"provider": profile.get("kind"), "api_key": profile["api_key"]}
        return capability.pi_model_listing(found.node, found.pi_cli, state.data_dir, llm)

    try:
        return {"models": model_list.list_models(profile, pi_listing=pi_listing, proxy=proxy)}
    except model_list.ModelListError as exc:
        return JSONResponse(
            {"code": exc.code, "status": exc.status, "reason": exc.reason, "detail": str(exc)}, status_code=502,
        )


@router.get("/api/settings/model-catalogue")
def model_catalogue(request: Request):
    """When the model catalogue was last fetched from pi.dev (PLAN 15.4.12); None before the first."""
    return {"updated_at": catalogue_update.updated_at(request.app.state.data_dir)}


@router.post("/api/settings/model-catalogue/refresh")
def refresh_model_catalogue(request: Request):
    """「更新模型目录」: fetch the catalogue, then write the model's parameters again (PLAN 15.4.12)."""
    state = request.app.state
    proxy = store.load(state.data_dir)["network"].get("proxy", "")
    result = catalogue_update.refresh(state.data_dir, pi_cli=_pi_cli(state), fetch=state.catalogue_fetch, proxy=proxy,
                                      providers=state.catalogue_providers)
    pi_models.refresh_custom_provider(state.data_dir, pi_cli=_pi_cli(state))
    return result


@router.post("/api/settings/model-info")
def model_info(request: Request, body: dict):
    """What Pi's bundled catalogue or the models.dev snapshot knows about one profile's model
    (PLAN 15.4.10): the page lists the thinking levels and pre-fills 「高级」 from it."""
    state = request.app.state
    profile = dict(body.get("profile") or {})
    # 「claude-opus-4-8[1m]」 is claude-opus-4-8 asked for with its 1M window (Claude Code's own suffix)
    profile["model"] = str(profile.get("model") or "").removesuffix("[1m]")
    source, fields = pi_models.model_fields(state.data_dir, profile, pi_cli=_pi_cli(state))
    if profile.get("agent") == "codex":  # Codex says which levels each of its models takes (15.4.13)
        known = next((model for model in state.agents.codex_models() if model["id"] == profile.get("model")), None)
        if known:  # the limits a blank 「高级」 box means: the same catalogue (agents/runs.py _limits)
            return {"source": "codex", "levels": known["levels"], "context_window": fields.get("contextWindow"),
                    "max_tokens": fields.get("maxTokens"), "thinking_level_map": None}
    return {
        "source": source, "context_window": fields.get("contextWindow"), "max_tokens": fields.get("maxTokens"),
        "thinking_level_map": fields.get("thinkingLevelMap"),
    }


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
            node_exe=str(found.node), pi_cli=str(found.pi_cli), agent_dir=probe_dir, agent=runs.agent_of(llm),
        )
    except (OneShotError, runs.AgentRunError) as exc:
        return JSONResponse({"ok": False, "detail": str(exc)[:200]}, status_code=200)
    if llm.get("agent", "pi") != "pi":  # Pi's own capability query does not speak for the other Agents
        images = bool((llm.get("custom") or {}).get("supports_images"))
    else:
        images = capability.query_supports_images(found.node, found.pi_cli, state.data_dir, llm)
    return JSONResponse(
        {"ok": True, "detail": f"{reply[:60]} · 支持看图：{'是' if images else '否'}"},
        status_code=200,
    )
