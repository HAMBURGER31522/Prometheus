"""Model profiles and the model list (PLAN 15.4.8). No real endpoint is ever called."""

import json

import pytest
from prometheus import paths
from prometheus.llm import model_list
from prometheus.settings import store

AUTH = {"Authorization": "Bearer test-token"}

CLAUDE = {"id": "claude", "name": "Claude 中转", "kind": "custom", "base_url": "https://relay.example/v1",
          "protocol": "anthropic", "api_key": "sk-claude-1111", "model": "claude-opus-4-8",
          "supports_images": True, "thinking": "medium"}
GPT = {"id": "gpt", "name": "GPT 中转", "kind": "custom", "base_url": "https://gpt.example/v1",
       "protocol": "openai", "api_key": "sk-gpt-2222", "model": "gpt-6-sol",
       "supports_images": True, "thinking": "high"}


def test_defaults_are_one_deepseek_profile_thinking_medium(tmp_path):
    settings = store.load(tmp_path)
    profiles = settings["llm_profiles"]
    assert profiles["active"] == profiles["items"][0]["id"]
    assert profiles["items"][0]["kind"] == "deepseek"
    assert settings["llm"]["thinking"] == "medium"


def test_an_old_single_model_setting_becomes_one_profile(tmp_path):
    paths.settings_file(tmp_path).write_text(json.dumps({"llm": {
        "provider": "custom", "model": "claude-opus-4-8", "api_key": "sk-old-9999", "thinking": "low",
        "custom": {"base_url": "https://api.justwoker.icu/v1", "supports_images": True, "protocol": "anthropic"},
    }}), encoding="utf-8")
    settings = store.load(tmp_path)
    [profile] = settings["llm_profiles"]["items"]
    assert profile["kind"] == "custom" and profile["protocol"] == "anthropic"
    assert profile["base_url"] == "https://api.justwoker.icu/v1" and profile["api_key"] == "sk-old-9999"
    assert profile["name"] == "api.justwoker.icu"
    assert settings["llm"]["model"] == "claude-opus-4-8" and settings["llm"]["thinking"] == "low"


def test_the_active_profile_drives_what_the_pipeline_reads(tmp_path):
    settings = store.load(tmp_path)
    settings["llm_profiles"] = {"active": "gpt", "items": [CLAUDE, GPT]}
    store.save(tmp_path, settings)
    llm = store.load(tmp_path)["llm"]
    assert llm["provider"] == "custom" and llm["model"] == "gpt-6-sol" and llm["api_key"] == "sk-gpt-2222"
    assert llm["custom"] == {"base_url": "https://gpt.example/v1", "supports_images": True, "protocol": "openai"}
    assert llm["thinking"] == "high"


def test_every_profile_key_is_masked_and_survives_a_masked_round_trip(client):
    body = client.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "claude", "items": [CLAUDE, GPT]}
    assert client.put("/api/settings", json=body, headers=AUTH).status_code == 200
    shown = client.get("/api/settings", headers=AUTH).json()
    assert [p["api_key"] for p in shown["llm_profiles"]["items"]] == ["****1111", "****2222"]
    assert client.put("/api/settings", json=shown, headers=AUTH).status_code == 200
    on_disk = json.loads(paths.settings_file(client.app.state.data_dir).read_text(encoding="utf-8"))
    assert [p["api_key"] for p in on_disk["llm_profiles"]["items"]] == ["sk-claude-1111", "sk-gpt-2222"]


class Fetch:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, url, headers, *, proxy=""):
        self.calls.append((url, headers))
        return self.payload


def test_openai_endpoints_list_models_with_a_bearer_key():
    fetch = Fetch({"data": [{"id": "gpt-6-sol"}, {"id": "gpt-5"}, {"id": "gpt-6-sol"}]})
    assert model_list.list_models(GPT, fetch=fetch) == ["gpt-5", "gpt-6-sol"]
    assert fetch.calls == [("https://gpt.example/v1/models", {"Authorization": "Bearer sk-gpt-2222"})]


def test_anthropic_endpoints_list_models_with_x_api_key():
    fetch = Fetch({"data": [{"id": "claude-opus-4-8", "type": "model"}]})
    assert model_list.list_models(CLAUDE, fetch=fetch) == ["claude-opus-4-8"]
    url, headers = fetch.calls[0]
    assert url == "https://relay.example/v1/models"
    assert headers["x-api-key"] == "sk-claude-1111" and headers["anthropic-version"] == "2023-06-01"


def test_builtin_providers_list_what_pi_knows():
    listing = (
        "provider  model              context  max-out  thinking  images\n"
        "deepseek  deepseek-flash     128K     8K       no        no\n"
        "deepseek  deepseek-reasoner  128K     8K       yes       no\n"
        "zhipu     glm-5              128K     8K       yes       yes\n"
    )
    profile = {**GPT, "kind": "deepseek"}
    assert model_list.list_models(profile, pi_listing=lambda: listing) == ["deepseek-flash", "deepseek-reasoner"]


def test_a_failing_endpoint_is_reported(client, monkeypatch):
    def broken(url, headers, *, proxy=""):
        raise OSError("401 Unauthorized")

    monkeypatch.setattr(model_list, "_fetch_json", broken)
    response = client.post("/api/settings/models", json={"profile": GPT}, headers=AUTH)
    assert response.status_code == 502
    assert response.json()["code"] == "MODEL_LIST_FAILED"


def test_a_masked_key_is_resolved_from_the_saved_profile(client, monkeypatch):
    body = client.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "gpt", "items": [GPT]}
    client.put("/api/settings", json=body, headers=AUTH)
    fetch = Fetch({"data": [{"id": "gpt-6-sol"}]})
    monkeypatch.setattr(model_list, "_fetch_json", fetch)
    response = client.post("/api/settings/models", json={"profile": {**GPT, "api_key": "****2222"}}, headers=AUTH)
    assert response.status_code == 200 and response.json() == {"models": ["gpt-6-sol"]}
    assert fetch.calls[0][1]["Authorization"] == "Bearer sk-gpt-2222"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to reach a real model endpoint")

    monkeypatch.setattr(model_list, "_fetch_json", refuse, raising=False)
