"""Model parameters in Pi's models.json (PLAN 15.4.10).

A custom model used to get only id / name / input, so Pi ran it with 128k context, 16k output
and budget-based thinking. The fields now come from the bundled Pi catalogue (pi-ai's
providers/data; a trimmed copy of real entries lives in fixtures/pi-catalogue), then from the
models.dev snapshot, and the profile's own numbers win.
"""

import json
import shutil
from pathlib import Path

import pytest
from prometheus import paths
from prometheus.llm import pi_catalogue, pi_models
from prometheus.runtime import Runtime
from prometheus.settings import store

AUTH = {"Authorization": "Bearer test-token"}
FIXTURE = Path(__file__).parent / "fixtures" / "pi-catalogue"
PI_AI_DATA = Path("@earendil-works") / "pi-ai" / "dist" / "providers" / "data"

RELAY = {"id": "relay", "name": "Claude 中转", "kind": "custom", "base_url": "https://api.justwoker.icu/v1",
         "protocol": "anthropic", "api_key": "sk-relay-1111", "model": "claude-opus-4-8",
         "supports_images": True, "thinking": "max"}
KIMI = {**RELAY, "id": "kimi", "name": "Kimi", "base_url": "https://api.moonshot.cn/v1", "protocol": "openai",
        "model": "kimi-k3"}
OPENAI = {**RELAY, "id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "protocol": "openai",
          "model": "gpt-5.6-sol"}
DOUBAO = {**RELAY, "id": "doubao", "name": "豆包", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
          "protocol": "openai", "model": "doubao-seed-2-1-pro-260628"}
UNKNOWN = "relay-private-model-x"


def pi_layout(root: Path, *, hoisted: bool = False) -> Path:
    """A Pi install shaped like the bundled one; returns its cli.js."""
    modules = root / "node_modules"
    package = modules / "@earendil-works" / "pi-coding-agent"
    cli = package / "dist" / "bundle" / "cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("", encoding="utf-8")
    shutil.copytree(FIXTURE, (modules if hoisted else package / "node_modules") / PI_AI_DATA)
    return cli


@pytest.fixture
def pi_cli(tmp_path):
    return pi_layout(tmp_path / "pi")


def data_dir_with(tmp_path, profile) -> Path:
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    pi_models.ensure_models_json(data_dir)
    settings = store.load(data_dir)
    settings["llm_profiles"] = {"active": profile["id"], "items": [profile]}
    store.save(data_dir, settings)
    return data_dir


def written(data_dir, pi_cli) -> dict:
    pi_models.apply_custom_provider(data_dir, store.load(data_dir)["llm"]["custom"], pi_cli=pi_cli)
    [entry] = json.loads(paths.models_json(data_dir).read_text(encoding="utf-8"))["providers"]["custom"]["models"]
    return entry


def test_claude_opus_4_8_runs_with_pis_own_parameters(tmp_path, pi_cli):
    entry = written(data_dir_with(tmp_path, RELAY), pi_cli)
    assert (entry.get("contextWindow"), entry.get("maxTokens")) == (1000000, 128000)
    assert entry.get("thinkingLevelMap") == {"xhigh": "xhigh", "max": "max"}
    # anthropic.json's entry, not opencode.json's (which lacks supportsStrictTools)
    assert entry.get("compat") == {"forceAdaptiveThinking": True, "supportsTemperature": False,
                                   "supportsStrictTools": True}
    assert entry["id"] == "claude-opus-4-8" and entry["input"] == ["text", "image"]


def test_an_address_on_a_catalogue_providers_site_takes_that_providers_entry(tmp_path, pi_cli):
    entry = written(data_dir_with(tmp_path, KIMI), pi_cli)
    # moonshotai-cn (api.moonshot.cn), not github-copilot, which comes first by name
    assert (entry.get("compat") or {}).get("deferredToolsMode") == "kimi"
    assert (entry.get("thinkingLevelMap") or {}).get("max") == "max"


def test_an_entry_for_another_api_gives_its_numbers_but_not_its_compat(tmp_path, pi_cli):
    # OpenAI's own entry speaks the Responses API; the profile speaks Chat Completions.
    entry = written(data_dir_with(tmp_path, OPENAI), pi_cli)
    assert (entry.get("contextWindow"), entry.get("maxTokens")) == (272000, 128000)
    assert (entry.get("thinkingLevelMap") or {}).get("xhigh") == "xhigh"
    assert "compat" not in entry


def test_models_dev_fills_in_the_limits_pi_does_not_know(tmp_path, pi_cli):
    entry = written(data_dir_with(tmp_path, {**DOUBAO, "thinking": "medium"}), pi_cli)
    assert (entry.get("contextWindow"), entry.get("maxTokens")) == (256000, 256000)
    assert "thinkingLevelMap" not in entry and "compat" not in entry


def test_the_fields_follow_the_model_and_an_unknown_model_gets_none(tmp_path, pi_cli):
    data_dir = data_dir_with(tmp_path, RELAY)
    assert written(data_dir, pi_cli).get("contextWindow") == 1000000
    settings = store.load(data_dir)
    settings["llm_profiles"]["items"][0].update(model=UNKNOWN, thinking="medium")
    store.save(data_dir, settings)
    entry = written(data_dir, pi_cli)
    assert entry["id"] == UNKNOWN
    assert set(entry) == {"id", "name", "reasoning", "input"}


def test_a_model_the_catalogue_lacks_gets_xhigh_and_max_as_chosen(tmp_path, pi_cli):
    """User 2026-09-29: the catalogue always lags the vendors; Pi runs xhigh / max only for a model
    whose thinkingLevelMap names them, so for an unknown one the level is declared as it is."""
    for thinking in ("max", "xhigh"):
        entry = written(data_dir_with(tmp_path / thinking, {**RELAY, "model": UNKNOWN, "thinking": thinking}), pi_cli)
        assert entry["thinkingLevelMap"] == {"xhigh": "xhigh", "max": "max"}
    doubao = written(data_dir_with(tmp_path / "doubao", DOUBAO), pi_cli)  # models.dev knows only its limits
    assert doubao["thinkingLevelMap"] == {"xhigh": "xhigh", "max": "max"} and doubao["contextWindow"] == 256000


def test_a_model_the_catalogue_knows_keeps_the_catalogues_levels(tmp_path, pi_cli):
    """A guard, not red: what the catalogue says about a known model is not overwritten."""
    relay = written(data_dir_with(tmp_path / "relay", RELAY), pi_cli)  # claude-opus-4-8, Pi's own entry
    assert relay["thinkingLevelMap"] == {"xhigh": "xhigh", "max": "max"}
    known = {**OPENAI, "thinking": "max"}
    data_dir = data_dir_with(tmp_path / "known", known)
    source, fields = pi_models.model_fields(data_dir, known, pi_cli=pi_cli)
    assert source == "pi"
    assert written(data_dir, pi_cli).get("thinkingLevelMap") == fields.get("thinkingLevelMap")


def test_the_profiles_own_numbers_take_precedence(tmp_path, pi_cli):
    entry = written(data_dir_with(tmp_path, {**RELAY, "context_window": 500000, "max_tokens": 64000}), pi_cli)
    assert (entry.get("contextWindow"), entry.get("maxTokens")) == (500000, 64000)
    assert (entry.get("compat") or {}).get("forceAdaptiveThinking") is True


def test_the_catalogue_is_found_next_to_the_pi_cli(tmp_path, pi_cli):
    nested = pi_cli.parents[2] / "node_modules" / PI_AI_DATA
    assert pi_catalogue.catalogue_dir(pi_cli) == nested
    hoisted = pi_layout(tmp_path / "hoisted", hoisted=True)
    assert pi_catalogue.catalogue_dir(hoisted) == tmp_path / "hoisted" / "node_modules" / PI_AI_DATA
    assert pi_catalogue.catalogue_dir(Path("cli.js")) is None
    assert pi_catalogue.catalogue_dir(None) is None


# ---- the settings API ----

@pytest.fixture
def with_pi(client, pi_cli, monkeypatch):
    runtime = Runtime(Path("node.exe"), pi_cli, Path("ffmpeg.exe"), Path("ffprobe.exe"))
    monkeypatch.setattr(client.app.state, "_runtime", runtime)
    return client


def test_model_info_says_what_the_catalogues_know(with_pi):
    info = with_pi.post("/api/settings/model-info", json={"profile": RELAY}, headers=AUTH).json()
    assert info == {"source": "pi", "context_window": 1000000, "max_tokens": 128000,
                    "thinking_level_map": {"xhigh": "xhigh", "max": "max"}}
    doubao = with_pi.post("/api/settings/model-info", json={"profile": DOUBAO}, headers=AUTH).json()
    assert doubao == {"source": "models.dev", "context_window": 256000, "max_tokens": 256000,
                      "thinking_level_map": None}
    unknown = with_pi.post("/api/settings/model-info", json={"profile": {**RELAY, "model": UNKNOWN}},
                           headers=AUTH).json()
    assert unknown == {"source": None, "context_window": None, "max_tokens": None, "thinking_level_map": None}


def test_model_info_for_a_builtin_provider_reads_what_pi_runs(with_pi):
    # The shipped models.json defines deepseek-flash (no 「中」); other DeepSeek models are Pi's own.
    flash = with_pi.post("/api/settings/model-info", json={"profile": store.DEFAULT_PROFILE}, headers=AUTH).json()
    assert flash["source"] == "pi"
    assert (flash["thinking_level_map"] or {}).get("max") == "max"
    assert "medium" in (flash["thinking_level_map"] or {}) and flash["thinking_level_map"]["medium"] is None
    pro = with_pi.post("/api/settings/model-info", json={"profile": {**store.DEFAULT_PROFILE, "model": "deepseek-v4-pro"}},
                       headers=AUTH).json()
    assert pro["source"] == "pi" and (pro["thinking_level_map"] or {}).get("high") == "high"


def test_saving_settings_writes_the_parameters(with_pi):
    body = with_pi.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "relay", "items": [RELAY]}
    assert with_pi.put("/api/settings", json=body, headers=AUTH).status_code == 200
    models = json.loads(paths.models_json(with_pi.app.state.data_dir).read_text(encoding="utf-8"))
    [entry] = models["providers"]["custom"]["models"]
    assert entry.get("contextWindow") == 1000000
    assert (entry.get("compat") or {}).get("forceAdaptiveThinking") is True


def test_startup_rewrites_the_custom_provider_from_the_saved_settings(tmp_path, pi_cli):
    """An install from before the model parameters gets them at the next start, without pressing 保存."""
    from prometheus.server import AppState

    data_dir = data_dir_with(tmp_path, RELAY)
    target = paths.models_json(data_dir)
    document = json.loads(target.read_text(encoding="utf-8"))
    document.setdefault("providers", {})["custom"] = {
        "baseUrl": "https://api.justwoker.icu", "api": "anthropic-messages", "apiKey": "$PI_API_KEY",
        "models": [{"id": "claude-opus-4-8", "name": "claude-opus-4-8", "reasoning": True, "input": ["text", "image"]}],
    }
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    state = AppState(True, found_runtime=Runtime(Path("node.exe"), pi_cli, Path("ffmpeg.exe"), Path("ffprobe.exe")))
    state.initialize(data_dir)
    try:
        entry = json.loads(target.read_text(encoding="utf-8"))["providers"]["custom"]["models"][0]
        assert entry["id"] == "claude-opus-4-8"
        assert entry.get("contextWindow") == 1000000
        assert entry.get("maxTokens") == 128000
        assert (entry.get("compat") or {}).get("forceAdaptiveThinking") is True
    finally:
        state.shutdown()


def test_startup_leaves_models_json_alone_for_a_builtin_provider(tmp_path, pi_cli):
    from prometheus.server import AppState

    data_dir = data_dir_with(tmp_path, {**RELAY, "id": "ds", "kind": "deepseek", "model": "deepseek-flash"})
    before = paths.models_json(data_dir).read_text(encoding="utf-8")
    state = AppState(True, found_runtime=Runtime(Path("node.exe"), pi_cli, Path("ffmpeg.exe"), Path("ffprobe.exe")))
    state.initialize(data_dir)
    try:
        after = paths.models_json(data_dir).read_text(encoding="utf-8")
        assert "custom" not in json.loads(after).get("providers", {}) or after == before
        assert json.loads(after)["providers"]["deepseek"] == json.loads(before)["providers"]["deepseek"]
    finally:
        state.shutdown()
