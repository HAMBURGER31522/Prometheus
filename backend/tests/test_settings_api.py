"""Settings persistence, key masking and models.json generation (PLAN 8.9)."""

import json

from prometheus import paths

AUTH = {"Authorization": "Bearer test-token"}


def test_defaults_round_trip_and_masking(client):
    body = {
        "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "sk-secret-1234",
                "thinking": "low", "custom": {"base_url": "", "supports_images": False}},
        "asr": {"backend": "local", "dashscope_api_key": "dash-key-5678",
                "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }
    saved = client.put("/api/settings", json=body, headers=AUTH)
    assert saved.status_code == 200

    loaded = client.get("/api/settings", headers=AUTH).json()
    assert loaded["llm"]["api_key"] == "****1234"
    assert loaded["asr"]["dashscope_api_key"] == "****5678"
    assert loaded["llm"]["model"] == "deepseek-flash"

    on_disk = json.loads(
        paths.settings_file(client.app.state.data_dir).read_text(encoding="utf-8")
    )
    assert on_disk["llm"]["api_key"] == "sk-secret-1234"


def test_masked_key_round_trip_keeps_stored_value(client):
    body = {
        "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "sk-secret-1234",
                "thinking": "low", "custom": {"base_url": "", "supports_images": False}},
        "asr": {"backend": "local", "dashscope_api_key": "dash-key-5678",
                "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }
    client.put("/api/settings", json=body, headers=AUTH)
    masked = client.get("/api/settings", headers=AUTH).json()
    saved = client.put("/api/settings", json=masked, headers=AUTH)
    assert saved.status_code == 200
    on_disk = json.loads(
        paths.settings_file(client.app.state.data_dir).read_text(encoding="utf-8")
    )
    assert on_disk["llm"]["api_key"] == "sk-secret-1234"
    assert on_disk["asr"]["dashscope_api_key"] == "dash-key-5678"


def test_cloud_backend_without_key_is_rejected(client):
    body = {
        "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "",
                "thinking": "low", "custom": {"base_url": "", "supports_images": False}},
        "asr": {"backend": "cloud", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }
    response = client.put("/api/settings", json=body, headers=AUTH)
    assert response.status_code == 422
    assert response.json() == {"code": "DASHSCOPE_KEY_REQUIRED"}


def test_backend_switch_preserves_saved_keys(client):
    body = {
        "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "sk-secret-1234",
                "thinking": "low", "custom": {"base_url": "", "supports_images": False}},
        "asr": {"backend": "local", "dashscope_api_key": "dash-key-5678",
                "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }
    client.put("/api/settings", json=body, headers=AUTH)
    masked = client.get("/api/settings", headers=AUTH).json()
    masked["asr"]["backend"] = "cloud"
    switched = client.put("/api/settings", json=masked, headers=AUTH)
    assert switched.status_code == 200
    on_disk = json.loads(
        paths.settings_file(client.app.state.data_dir).read_text(encoding="utf-8")
    )
    assert on_disk["asr"]["backend"] == "cloud"
    assert on_disk["asr"]["dashscope_api_key"] == "dash-key-5678"


def test_backend_only_accepts_local_or_cloud(client):
    masked = client.get("/api/settings", headers=AUTH).json()
    masked["asr"]["backend"] = "mlx"
    response = client.put("/api/settings", json=masked, headers=AUTH)
    assert response.status_code == 422


def test_first_run_copies_models_json(client):
    models_json = paths.models_json(client.app.state.data_dir)
    assert models_json.is_file()
    providers = json.loads(models_json.read_text(encoding="utf-8"))["providers"]
    assert "deepseek" in providers
    assert "zhipu" in providers


def test_custom_provider_is_written_to_models_json(client):
    body = {
        "llm": {"provider": "custom", "model": "my-model", "api_key": "sk-abc",
                "thinking": "low",
                "custom": {"base_url": "https://api.example.com/v1", "supports_images": True}},
        "asr": {"backend": "local", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }
    assert client.put("/api/settings", json=body, headers=AUTH).status_code == 200
    models_json = paths.models_json(client.app.state.data_dir)
    providers = json.loads(models_json.read_text(encoding="utf-8"))["providers"]
    custom = providers["custom"]
    assert custom["api"] == "openai-completions"
    assert custom["baseUrl"] == "https://api.example.com/v1"
    assert custom["models"][0]["id"] == "my-model"
    assert "image" in custom["models"][0]["input"]


def _custom_body(protocol, base_url):
    return {
        "llm": {"provider": "custom", "model": "claude-opus-4-8", "api_key": "sk-abc",
                "thinking": "low",
                "custom": {"base_url": base_url, "supports_images": True, "protocol": protocol}},
        "asr": {"backend": "local", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
        "network": {"proxy": "", "youtube_cookies_file": ""},
        "figures_default": True,
    }


def test_custom_anthropic_protocol_writes_anthropic_messages(client):
    body = _custom_body("anthropic", "https://api.justwoker.icu/v1")
    assert client.put("/api/settings", json=body, headers=AUTH).status_code == 200
    models_json = paths.models_json(client.app.state.data_dir)
    custom = json.loads(models_json.read_text(encoding="utf-8"))["providers"]["custom"]
    assert custom["api"] == "anthropic-messages"
    assert custom["baseUrl"] == "https://api.justwoker.icu"


def test_custom_protocol_must_be_openai_or_anthropic(client):
    response = client.put("/api/settings", json=_custom_body("grpc", "https://x.example"), headers=AUTH)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PROTOCOL"


def test_test_model_reports_image_support_from_the_data_dir_config(client, monkeypatch):
    import subprocess

    from prometheus import paths
    from prometheus.api import settings as settings_api

    assert client.put("/api/settings", json=_custom_body("anthropic", "https://api.justwoker.icu"),
                      headers=AUTH).status_code == 200
    expected_dir = str(paths.pi_config_dir(client.app.state.data_dir))
    listing = ("provider  model            context  max-out  thinking  images\n"
               "custom    claude-opus-4-8  200K     32K      yes       yes\n")

    def fake_run(command, **kwargs):
        env = kwargs.get("env") or {}
        # Without the data-dir config Pi cannot see the custom provider at all.
        out = listing if env.get("PI_CODING_AGENT_DIR") == expected_dir else "No models available."
        return subprocess.CompletedProcess(command, 0, out.encode(), b"")

    monkeypatch.setattr(settings_api, "run_one_shot", lambda *a, **k: "可用", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    detail = client.post("/api/settings/test-model", headers=AUTH).json()["detail"]
    assert detail.endswith("支持看图：是")
