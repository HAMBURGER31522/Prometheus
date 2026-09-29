"""Codex CLI's own view of models and login (PLAN 15.4.13): 「获取模型列表」 and the thinking levels per
model come from its app-server (``model/list``, with each model's supported reasoning efforts; the
ChatGPT account's own list once signed in), the login state from ``codex login status``, and
「登录 ChatGPT 账户」 starts ``codex login`` in the app's own CODEX_HOME."""

import json
import subprocess
from pathlib import Path

from prometheus.agents import codex_app, commands

AUTH = {"Authorization": "Bearer test-token"}
TOOLS = Path("T:/tools")
CONFIG = Path("D:/data/.prometheus/config")
PAGE_ONE = {"data": [
    {"id": "gpt-6-astra", "displayName": "gpt-6-astra", "hidden": False, "defaultReasoningEffort": "low",
     "supportedReasoningEfforts": [{"reasoningEffort": level, "description": ""} for level in
                                   ("low", "medium", "high", "xhigh", "max", "ultra")],
     "inputModalities": ["text", "image"]},
    {"id": "gpt-old", "displayName": "gpt-old", "hidden": True, "defaultReasoningEffort": "medium",
     "supportedReasoningEfforts": [], "inputModalities": ["text"]}], "nextCursor": "page-2"}
PAGE_TWO = {"data": [
    {"id": "gpt-5.5", "displayName": "gpt-5.5", "hidden": False, "defaultReasoningEffort": "medium",
     "supportedReasoningEfforts": [{"reasoningEffort": level, "description": ""} for level in ("low", "medium")],
     "inputModalities": ["text"]}], "nextCursor": None}


class FakeAppServer:
    """codex app-server over stdio: answers initialize and two pages of model/list."""

    def __init__(self, command, **kwargs):
        self.command, self.env = command, kwargs.get("env")
        self.sent, self._out = [], []
        self.stdin = self
        self.stdout = self

    def write(self, data: bytes):
        message = json.loads(data)
        self.sent.append(message)
        if message.get("method") == "initialize":
            self._out.append({"id": message["id"], "result": {"codexHome": "x"}})
            self._out.append({"method": "remoteControl/status/changed", "params": {}})
        elif message.get("method") == "model/list":
            page = PAGE_TWO if (message.get("params") or {}).get("cursor") == "page-2" else PAGE_ONE
            self._out.append({"id": message["id"], "result": page})

    def flush(self):
        pass

    def readline(self) -> bytes:
        return (json.dumps(self._out.pop(0)) + "\n").encode() if self._out else b""

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def test_the_model_list_comes_from_codex_with_the_levels_each_model_takes(monkeypatch):
    started = []
    monkeypatch.setattr(codex_app.subprocess, "Popen",
                        lambda command, **kwargs: started.append(FakeAppServer(command, **kwargs)) or started[-1])
    models = codex_app.models(TOOLS, CONFIG)
    assert [model["id"] for model in models] == ["gpt-6-astra", "gpt-5.5"]  # hidden ones left out
    assert models[0]["levels"] == ["low", "medium", "high", "xhigh", "max"]  # ours only; no 「ultra」
    assert models[0]["images"] is True and models[1]["images"] is False
    server = started[0]
    assert server.command[:2] == [str(commands.executable(TOOLS, "codex")), "app-server"]
    assert server.env["CODEX_HOME"] == str(CONFIG / "codex")
    assert [message.get("method") for message in server.sent][:3] == ["initialize", "initialized", "model/list"]


def test_the_login_state_is_what_codex_login_status_says(monkeypatch):
    answers = iter([0, 1])
    seen = []

    def fake_run(command, **kwargs):
        seen.append((command, kwargs["env"]["CODEX_HOME"]))
        return subprocess.CompletedProcess(command, next(answers), b"", b"")

    monkeypatch.setattr(codex_app.subprocess, "run", fake_run)
    assert codex_app.logged_in(TOOLS, CONFIG) is True
    assert codex_app.logged_in(TOOLS, CONFIG) is False
    assert seen[0][0][1:] == ["login", "status"] and seen[0][1] == str(CONFIG / "codex")


def test_signing_in_starts_codex_login_in_the_apps_own_codex_home(monkeypatch):
    started = []

    class Login:
        def __init__(self, command, **kwargs):
            started.append((command, kwargs))

        def poll(self):
            return None

    monkeypatch.setattr(codex_app.subprocess, "Popen", Login)
    codex_app.start_login(TOOLS, CONFIG)
    codex_app.start_login(TOOLS, CONFIG)  # still waiting for the browser: not a second one
    assert len(started) == 1
    command, kwargs = started[0]
    assert command == [str(commands.executable(TOOLS, "codex")), "login"]
    assert kwargs["env"]["CODEX_HOME"] == str(CONFIG / "codex") and "OPENAI_API_KEY" not in kwargs["env"]


CODEX_PROFILE = {"id": "p1", "name": "Codex", "kind": "custom", "base_url": "", "protocol": "openai", "api_key": "",
                 "model": "gpt-6-astra", "supports_images": True, "thinking": "medium", "context_window": None,
                 "max_tokens": None, "agent": "codex", "access": "login"}


def test_the_settings_page_lists_codex_models_and_their_levels_from_codex(client_factory, tmp_path, monkeypatch):
    client = client_factory(data_dir=tmp_path / "data", fake=False)
    listed = [{"id": "gpt-6-astra", "levels": ["low", "medium", "high"], "images": True}]
    monkeypatch.setattr(codex_app, "models", lambda tools_root, config_root: listed)
    assert client.post("/api/settings/models", json={"profile": CODEX_PROFILE}, headers=AUTH).json() == {
        "models": ["gpt-6-astra"]}
    info = client.post("/api/settings/model-info", json={"profile": CODEX_PROFILE}, headers=AUTH).json()
    assert info["source"] == "codex" and info["levels"] == ["low", "medium", "high"]
