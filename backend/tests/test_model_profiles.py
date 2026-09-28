"""Model profiles and the model list (PLAN 15.4.8, 15.4.10). No real endpoint is ever called."""

import contextlib
import email.message
import importlib.metadata
import io
import json
import urllib.error

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
    paths.init_data_dir(tmp_path)
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
    paths.init_data_dir(tmp_path)
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
    [(url, headers)] = fetch.calls
    assert url == "https://gpt.example/v1/models" and headers["Authorization"] == "Bearer sk-gpt-2222"


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


# ---- R7d (PLAN 15.4.10): keys are never sent back, so an empty field means 「不修改」 ----

def test_an_empty_key_keeps_the_saved_one_and_a_typed_key_replaces_it(client):
    body = client.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "claude", "items": [CLAUDE, GPT]}
    client.put("/api/settings", json=body, headers=AUTH)
    shown = client.get("/api/settings", headers=AUTH).json()
    shown["llm_profiles"]["items"][0]["api_key"] = ""
    shown["llm_profiles"]["items"][1]["api_key"] = "sk-gpt-new-3333"
    assert client.put("/api/settings", json=shown, headers=AUTH).status_code == 200
    on_disk = json.loads(paths.settings_file(client.app.state.data_dir).read_text(encoding="utf-8"))
    assert [p["api_key"] for p in on_disk["llm_profiles"]["items"]] == ["sk-claude-1111", "sk-gpt-new-3333"]


def test_an_empty_key_field_lists_models_with_the_saved_key(client, monkeypatch):
    body = client.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "gpt", "items": [GPT]}
    client.put("/api/settings", json=body, headers=AUTH)
    fetch = Fetch({"data": [{"id": "gpt-6-sol"}]})
    monkeypatch.setattr(model_list, "_fetch_json", fetch)
    response = client.post("/api/settings/models", json={"profile": {**GPT, "api_key": ""}}, headers=AUTH)
    assert response.status_code == 200
    assert fetch.calls[0][1]["Authorization"] == "Bearer sk-gpt-2222"


def test_profiles_keep_their_context_window_and_max_output(tmp_path):
    paths.init_data_dir(tmp_path)
    settings = store.load(tmp_path)
    settings["llm_profiles"] = {"active": "claude", "items": [
        {**CLAUDE, "context_window": 500000, "max_tokens": 64000},
        {**GPT, "context_window": "lots", "max_tokens": -5},
    ]}
    store.save(tmp_path, settings)
    claude, gpt = store.load(tmp_path)["llm_profiles"]["items"]
    assert (claude.get("context_window"), claude.get("max_tokens")) == (500000, 64000)
    assert "context_window" in gpt and (gpt["context_window"], gpt["max_tokens"]) == (None, None)


# ---- 「获取模型列表」 failures say why (PLAN 15.4.10) ----

def http_error(status, body=b"", **headers):
    message = email.message.Message()
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    return urllib.error.HTTPError("https://relay.example/v1/models", status, "error", message, io.BytesIO(body))


class Replies:
    """A fake fetch that answers each call with the next reply (a payload or an exception)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, url, headers, *, proxy=""):
        self.calls.append((url, headers))
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def test_requests_carry_a_prometheus_user_agent():
    fetch = Fetch({"data": [{"id": "gpt-6-sol"}]})
    model_list.list_models(GPT, fetch=fetch)
    agent = fetch.calls[0][1].get("User-Agent", "")
    assert agent == f"Prometheus/{importlib.metadata.version('prometheus-backend')}"
    assert "urllib" not in agent.lower()


def test_an_openai_address_without_v1_is_tried_again_under_v1():
    fetch = Replies(http_error(404), {"data": [{"id": "gpt-6-sol"}]})
    models = None
    with contextlib.suppress(model_list.ModelListError):
        models = model_list.list_models({**GPT, "base_url": "https://relay.example/"}, fetch=fetch)
    assert [url for url, _ in fetch.calls] == ["https://relay.example/models", "https://relay.example/v1/models"]
    assert models == ["gpt-6-sol"]


def test_an_address_already_ending_in_v1_is_not_tried_twice():
    fetch = Replies(http_error(404), {"data": [{"id": "gpt-6-sol"}]})
    with pytest.raises(model_list.ModelListError) as caught:
        model_list.list_models(GPT, fetch=fetch)
    assert (caught.value.status, caught.value.reason) == (404, "这个地址没有模型列表接口")
    assert [url for url, _ in fetch.calls] == ["https://gpt.example/v1/models"]


CLOUDFLARE_PAGE = b"<html><title>Attention Required! | Cloudflare</title><p>Sorry, you have been blocked</p></html>"


@pytest.mark.parametrize(("failure", "status", "reason"), [
    (http_error(401, b'{"error": {"message": "invalid key"}}'), 401, "Key 无效或无权限"),
    (http_error(403, b'{"error": {"type": "permission_error"}}', server="cloudflare"), 403, "Key 无效或无权限"),
    (http_error(403, b"error code: 1010", server="cloudflare"), 403, "请求被 Cloudflare 拦截"),
    (http_error(403, CLOUDFLARE_PAGE), 403, "请求被 Cloudflare 拦截"),
    (http_error(500, b"upstream exploded"), 500, "请求失败"),
    (TimeoutError("timed out"), None, "连接超时"),
    (urllib.error.URLError(TimeoutError("timed out")), None, "连接超时"),
])
def test_a_failure_carries_the_status_and_a_short_reason(failure, status, reason):
    with pytest.raises(model_list.ModelListError) as caught:
        model_list.list_models(CLAUDE, fetch=Replies(failure))
    assert (caught.value.status, caught.value.reason) == (status, reason)


def test_the_settings_api_returns_the_status_and_reason(client, monkeypatch):
    monkeypatch.setattr(model_list, "_fetch_json", Replies(http_error(401, b'{"error": "bad key"}')))
    response = client.post("/api/settings/models", json={"profile": GPT}, headers=AUTH)
    assert response.status_code == 502 and response.json()["code"] == "MODEL_LIST_FAILED"
    assert (response.json().get("status"), response.json().get("reason")) == (401, "Key 无效或无权限")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to reach a real model endpoint")

    monkeypatch.setattr(model_list, "_fetch_json", refuse, raising=False)


def test_the_eye_reveals_a_profiles_saved_key_and_only_that_one(client):
    """「显示 API Key」(PLAN 15.4.10, user 2026-09-28): the full key comes back only when asked for."""
    body = client.get("/api/settings", headers=AUTH).json()
    body["llm_profiles"] = {"active": "claude", "items": [CLAUDE, GPT]}
    client.put("/api/settings", json=body, headers=AUTH)
    assert client.get("/api/settings", headers=AUTH).json()["llm_profiles"]["items"][1]["api_key"] == "****2222"
    response = client.post("/api/settings/reveal-key", json={"profile_id": "gpt"}, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"api_key": "sk-gpt-2222"}
    assert client.post("/api/settings/reveal-key", json={"profile_id": "nope"}, headers=AUTH).status_code == 404
    assert client.post("/api/settings/reveal-key", json={"profile_id": "gpt"}).status_code == 401


def test_the_eye_reveals_the_custom_transcription_key(client):
    body = client.get("/api/settings", headers=AUTH).json()
    body["asr"]["custom"] = {"base_url": "https://asr.example.com/v1", "api_key": "sk-asr-7777", "model": "whisper-1"}
    client.put("/api/settings", json=body, headers=AUTH)
    response = client.post("/api/settings/reveal-key", json={"target": "asr"}, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"api_key": "sk-asr-7777"}
