"""Updating the model catalogue from pi.dev (PLAN 15.4.12).

The bundled Pi's catalogue is from 2026-09-04 and did not know gpt-6-luna, so Pi ran 「最高」 as
「高」 and the context came from the models.dev snapshot (1050000 instead of 272000). Pi refreshes
its catalogue from pi.dev itself only when online and only for providers with credentials; the
app fetches the same public files for every bundled provider and prefers them.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from prometheus import paths
from prometheus.llm import catalogue_update, pi_models
from prometheus.runtime import Runtime
from test_model_params import AUTH, data_dir_with, pi_layout

CPA = {"id": "cpa", "name": "CPA GPT", "kind": "custom", "base_url": "http://127.0.0.1:8317/v1", "protocol": "openai",
       "api_key": "sk-cpa-2222", "model": "gpt-6-luna", "supports_images": True, "thinking": "max"}
LUNA = {"id": "gpt-6-luna", "name": "GPT-6 Luna", "api": "openai-responses", "provider": "openai",
        "baseUrl": "https://api.openai.com/v1", "reasoning": True, "input": ["text", "image"],
        "contextWindow": 272000, "maxTokens": 128000,
        "thinkingLevelMap": {"off": "none", "minimal": None, "low": "low", "medium": "medium", "high": "high",
                             "xhigh": "xhigh", "max": "max"}}
PI_DEV = {"openai": {"gpt-6-luna": LUNA}, "anthropic": {}}
NOW = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)


@pytest.fixture
def pi_cli(tmp_path):
    return pi_layout(tmp_path / "pi")


def fetcher(catalogues: dict, calls: list):
    def fetch(url: str, *, proxy: str = ""):
        provider = url.rstrip("/").rsplit("/", 1)[1]
        calls.append((url, proxy))
        if provider not in catalogues:
            raise OSError("offline")
        return catalogues[provider]

    return fetch


def test_every_bundled_provider_is_fetched_from_pi_dev_and_the_time_is_kept(tmp_path, pi_cli):
    data_dir, calls = data_dir_with(tmp_path, CPA), []
    result = catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher(PI_DEV, calls),
                                      proxy="http://127.0.0.1:7890", now=NOW)
    bundled = sorted(path.stem for path in catalogue_update.bundled_providers(pi_cli))
    assert sorted(url.rsplit("/", 1)[1] for url, _ in calls) == bundled
    assert all(url.startswith("https://pi.dev/api/models/providers/") for url, _ in calls)
    assert {proxy for _, proxy in calls} == {"http://127.0.0.1:7890"}
    assert result == {"updated_at": NOW.isoformat(), "providers": 2,
                      "failed": sorted(set(bundled) - {"openai", "anthropic"})}
    assert json.loads((catalogue_update.catalogue_folder(data_dir) / "openai.json").read_text(encoding="utf-8")) == \
        PI_DEV["openai"]
    assert catalogue_update.updated_at(data_dir) == NOW.isoformat()


def test_a_provider_that_fails_keeps_its_last_catalogue(tmp_path, pi_cli):
    data_dir = data_dir_with(tmp_path, CPA)
    catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher(PI_DEV, []), now=NOW)
    later = NOW + timedelta(days=2)
    result = catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher({}, []), now=later)
    assert result["providers"] == 0 and "openai" in result["failed"]
    assert json.loads((catalogue_update.catalogue_folder(data_dir) / "openai.json").read_text(encoding="utf-8")) == \
        PI_DEV["openai"]
    assert catalogue_update.updated_at(data_dir) == NOW.isoformat()  # nothing new arrived


def test_the_fresh_catalogue_wins_so_luna_runs_at_max_with_its_real_context(tmp_path, pi_cli):
    data_dir = data_dir_with(tmp_path, CPA)
    _, before = pi_models.model_fields(data_dir, CPA, pi_cli=pi_cli)
    assert (before.get("thinkingLevelMap") or {}).get("max") is None
    catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher(PI_DEV, []), now=NOW)
    source, after = pi_models.model_fields(data_dir, CPA, pi_cli=pi_cli)
    assert source == "pi"
    assert after["contextWindow"] == 272000 and after["thinkingLevelMap"]["max"] == "max"
    assert "compat" not in after  # written for the Responses API, not for our Chat Completions


def test_the_fresh_catalogue_replaces_the_bundled_entry_of_the_same_provider(tmp_path, pi_cli):
    bundled = json.loads((catalogue_update.bundled_providers(pi_cli)[0].parent / "openai.json").read_text(encoding="utf-8"))
    api, entries = next((api, entries) for api, entries in bundled.items() if entries)
    model_id, entry = next(iter(entries.items()))
    data_dir = data_dir_with(tmp_path, {**CPA, "model": model_id})
    newer = {model_id: {**entry, "id": model_id, "api": api, "provider": "openai", "contextWindow": 123456}}
    catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher({"openai": newer}, []), now=NOW)
    _, fields = pi_models.model_fields(data_dir, {**CPA, "model": model_id}, pi_cli=pi_cli)
    assert fields["contextWindow"] == 123456


def test_a_catalogue_older_than_a_day_is_due(tmp_path, pi_cli):
    data_dir = data_dir_with(tmp_path, CPA)
    assert catalogue_update.due(data_dir, now=NOW)
    catalogue_update.refresh(data_dir, pi_cli=pi_cli, fetch=fetcher(PI_DEV, []), now=NOW)
    assert not catalogue_update.due(data_dir, now=NOW + timedelta(hours=23))
    assert catalogue_update.due(data_dir, now=NOW + timedelta(hours=25))


# ---- the settings API ----

@pytest.fixture
def with_pi(client, pi_cli, monkeypatch):
    runtime = Runtime(__import__("pathlib").Path("node.exe"), pi_cli, None, None)
    monkeypatch.setattr(client.app.state, "_runtime", runtime)
    monkeypatch.setattr(client.app.state, "catalogue_fetch", fetcher(PI_DEV, []))
    return client


def test_the_button_updates_the_catalogue_and_rewrites_models_json(with_pi):
    body = with_pi.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "cpa", "items": [CPA]}
    assert with_pi.put("/api/settings", json=body, headers=AUTH).status_code == 200
    assert with_pi.get("/api/settings/model-catalogue", headers=AUTH).json() == {"updated_at": None}
    result = with_pi.post("/api/settings/model-catalogue/refresh", headers=AUTH).json()
    assert result["providers"] == 2 and result["updated_at"]
    assert with_pi.get("/api/settings/model-catalogue", headers=AUTH).json() == {"updated_at": result["updated_at"]}
    models = json.loads(paths.models_json(with_pi.app.state.data_dir).read_text(encoding="utf-8"))
    [entry] = models["providers"]["custom"]["models"]
    assert entry["contextWindow"] == 272000 and entry["thinkingLevelMap"]["max"] == "max"
    info = with_pi.post("/api/settings/model-info", json={"profile": CPA}, headers=AUTH).json()
    assert info["source"] == "pi" and info["thinking_level_map"]["max"] == "max"


def test_startup_updates_a_catalogue_older_than_a_day_in_the_background(tmp_path, pi_cli):
    from pathlib import Path

    from prometheus.server import AppState

    data_dir = data_dir_with(tmp_path, CPA)
    state = AppState(True, found_runtime=Runtime(Path("node.exe"), pi_cli, None, None))
    state.catalogue_fetch = fetcher(PI_DEV, [])
    state.initialize(data_dir)
    try:
        state.catalogue_thread.join(timeout=10)
        assert catalogue_update.updated_at(data_dir) is not None
        [entry] = json.loads(paths.models_json(data_dir).read_text(encoding="utf-8"))["providers"]["custom"]["models"]
        assert entry["thinkingLevelMap"]["max"] == "max"
    finally:
        state.shutdown()
