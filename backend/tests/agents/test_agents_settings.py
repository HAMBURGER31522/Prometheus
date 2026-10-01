"""Every model profile names its Agent and how it connects (PLAN 15.4.13): Pi, Codex CLI or
Claude Code; 「接口 + Key」 for all three, 「官方登录」 only for Codex CLI."""

import json

from prometheus import paths
from prometheus.settings import store

AUTH = {"Authorization": "Bearer test-token"}


def _profile(**fields):
    return {"id": "p1", "name": "中转", "kind": "custom", "base_url": "https://relay.example/v1", "protocol": "openai",
            "api_key": "sk-test-0000", "model": "m", "supports_images": False, "thinking": "medium",
            "context_window": None, "max_tokens": None, "agent": "pi", "access": "key", **fields}


def _put(client, profile):
    body = {"llm_profiles": {"active": profile["id"], "items": [profile]}, "asr": {"backend": "local"},
            "network": {"proxy": "", "youtube_cookies_file": ""}, "figures_default": True}
    return client.put("/api/settings", json=body, headers=AUTH)


def test_profiles_saved_before_agents_run_on_pi_with_a_key(tmp_path):
    old = {key: value for key, value in _profile().items() if key not in ("agent", "access")}
    file = paths.settings_file(tmp_path)
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({"llm_profiles": {"active": "p1", "items": [old]}}), encoding="utf-8")
    item = store.load(tmp_path)["llm_profiles"]["items"][0]
    assert (item.get("agent"), item.get("access")) == ("pi", "key")


def test_claude_code_takes_only_the_anthropic_protocol(client):
    refused = _put(client, _profile(agent="claude", protocol="openai"))
    assert refused.status_code == 422 and refused.json()["code"] == "AGENT_PROTOCOL_MISMATCH"
    assert _put(client, _profile(agent="claude", protocol="anthropic")).status_code == 200
    assert client.get("/api/settings", headers=AUTH).json()["llm_profiles"]["items"][0].get("agent") == "claude"


def test_codex_takes_only_the_openai_protocol(client):
    refused = _put(client, _profile(agent="codex", protocol="anthropic"))
    assert refused.status_code == 422 and refused.json()["code"] == "AGENT_PROTOCOL_MISMATCH"
    assert _put(client, _profile(agent="codex", protocol="openai")).status_code == 200


def test_codex_and_claude_code_need_an_endpoint_of_their_own(client):
    """DeepSeek and 智谱 as built-in kinds are Pi's own providers; the other Agents need an address."""
    refused = _put(client, _profile(agent="claude", kind="deepseek", protocol="anthropic"))
    assert refused.status_code == 422 and refused.json()["code"] == "AGENT_NEEDS_ENDPOINT"


def test_only_codex_signs_in_with_an_official_account(client):
    refused = _put(client, _profile(agent="claude", protocol="anthropic", access="login"))
    assert refused.status_code == 422 and refused.json()["code"] == "INVALID_ACCESS"
    signed_in = _profile(agent="codex", access="login", base_url="", api_key="")
    assert _put(client, signed_in).status_code == 200
    saved = client.get("/api/settings", headers=AUTH).json()["llm_profiles"]["items"][0]
    assert (saved.get("agent"), saved.get("access")) == ("codex", "login")


def test_an_unknown_agent_is_refused(client):
    refused = _put(client, _profile(agent="gemini"))
    assert refused.status_code == 422 and refused.json()["code"] == "INVALID_AGENT"
