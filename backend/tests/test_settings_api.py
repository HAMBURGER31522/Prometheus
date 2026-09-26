"""Settings persistence, key masking and models.json generation (PLAN 8.9)."""

import json

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
        (client.app.state.data_dir / "config" / "settings.json").read_text(encoding="utf-8")
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
        (client.app.state.data_dir / "config" / "settings.json").read_text(encoding="utf-8")
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
        (client.app.state.data_dir / "config" / "settings.json").read_text(encoding="utf-8")
    )
    assert on_disk["asr"]["backend"] == "cloud"
    assert on_disk["asr"]["dashscope_api_key"] == "dash-key-5678"


def test_backend_only_accepts_local_or_cloud(client):
    masked = client.get("/api/settings", headers=AUTH).json()
    masked["asr"]["backend"] = "mlx"
    response = client.put("/api/settings", json=masked, headers=AUTH)
    assert response.status_code == 422


def test_first_run_copies_models_json(client):
    models_json = client.app.state.data_dir / "config" / "pi" / "models.json"
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
    models_json = client.app.state.data_dir / "config" / "pi" / "models.json"
    providers = json.loads(models_json.read_text(encoding="utf-8"))["providers"]
    custom = providers["custom"]
    assert custom["api"] == "openai-completions"
    assert custom["baseUrl"] == "https://api.example.com/v1"
    assert custom["models"][0]["id"] == "my-model"
    assert "image" in custom["models"][0]["input"]
