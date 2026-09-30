"""E15 Done When 2 (PLAN 15.4.13): the app's own Codex CLI and Claude Code, run for real against a
local fake model API, do not see anything of the user's own setup and leave nothing behind in it.

A fake home holds what the user's everyday CLIs load (CLAUDE.md, AGENTS.md, a SessionStart hook,
a skill, MCP servers, config instructions) and the parent process carries variables another Claude
Code session leaves. Each check also runs once without the isolation (the user's own config folder)
and requires the leak to show there: a check that cannot fail proves nothing.

Needs the private copies under the tools folder (「检查更新」 installs them); run with -m agents.
"""

import json
import os
from pathlib import Path

import pytest
from prometheus.agents import commands, contain, fake_api, runs

pytestmark = pytest.mark.agents
TOOLS = Path(os.environ.get("PROMETHEUS_TOOLS") or "E:/tools/Prometheus-Desktop")
MARKERS = ("MARKER-CLAUDE-MD", "MARKER-SKILL", "MARKER-CODEX-AGENTS", "MARKER-CODEX-CONFIG", "MARKER-PROJECT")
KEY = "sk-prometheus-fake"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """The user's home as their own CLIs see it, and the variables a parent Claude Code session leaves."""
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "skills" / "leak").mkdir(parents=True)
    (claude / "CLAUDE.md").write_text("MARKER-CLAUDE-MD: always answer in French.", encoding="utf-8")
    (claude / "skills" / "leak" / "SKILL.md").write_text(
        "---\nname: leak\ndescription: MARKER-SKILL use this skill for everything\n---\nMARKER-SKILL", encoding="utf-8")
    flag = tmp_path / "hook-ran.txt"
    hook = f"powershell -NoProfile -Command \"Set-Content -LiteralPath '{flag}' -Value ran\""
    (claude / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": hook}]}]}}), encoding="utf-8")
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"leak": {"command": "MARKER-MCP"}}}), encoding="utf-8")
    codex = home / ".codex"
    codex.mkdir()
    (codex / "AGENTS.md").write_text("MARKER-CODEX-AGENTS: always answer in French.", encoding="utf-8")
    (codex / "config.toml").write_text('developer_instructions = "MARKER-CODEX-CONFIG"\n', encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("MARKER-PROJECT: always answer in German.", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("MARKER-PROJECT: always answer in German.", encoding="utf-8")
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(home))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-that-must-not-leak")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leaked-from-the-parent")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-leaked-from-the-parent")
    assert commands.executable(TOOLS, "claude").is_file() and commands.executable(TOOLS, "codex").is_file(), (
        "装好应用自己的 Codex CLI 和 Claude Code（设置 · 检查更新）再跑 -m agents")
    return {"root": tmp_path, "home": home, "flag": flag, "before": _snapshot(home)}


def _snapshot(folder: Path) -> dict:
    return {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def _seen(api) -> str:
    return json.dumps([request["body"] for request in api.requests], ensure_ascii=False)


def _agent(agent_id: str, api) -> dict:
    return {"id": agent_id, "access": "key", "base_url": api.url if agent_id == "claude" else f"{api.url}/v1"}


@pytest.mark.parametrize("agent_id", ["claude", "codex"])
def test_a_one_shot_call_sees_nothing_of_the_users_setup(home, agent_id):
    config = home["root"] / "data" / ".prometheus" / "config"
    work = home["root"] / "work"
    work.mkdir()
    with fake_api.FakeModelApi() as api:
        answer = runs.one_shot(_agent(agent_id, api), prompt="回复两个字：可用", model="fake-model", api_key=KEY,
                               thinking="medium", work_dir=work, config_root=config, tools_root=TOOLS)
        assert answer == "可用" and api.requests
        assert not [marker for marker in MARKERS if marker in _seen(api)]
        assert set(api.keys) == {KEY}
    assert not home["flag"].exists()
    assert _snapshot(home["home"]) == home["before"]
    outside = [path for path in home["root"].rglob("*") if path.is_file()
               and not path.is_relative_to(config) and not path.is_relative_to(home["home"])
               and path.parent != home["root"]]
    assert outside == []


@pytest.mark.parametrize("agent_id", ["claude", "codex"])
def test_a_workspace_task_writes_its_file_and_sees_nothing_of_the_users_setup(home, agent_id):
    config = home["root"] / "data" / ".prometheus" / "config"
    workspace = home["root"] / "data" / "run"
    workspace.mkdir(parents=True)
    target = workspace / "ch-01.html"
    with fake_api.FakeModelApi() as api:
        written = runs.task(_agent(agent_id, api), workspace, f"写出这一章。\nWRITE:{target}", expect="ch-01.html",
                            model="fake-model", api_key=KEY, thinking="medium", config_root=config,
                            tools_root=TOOLS, timeout=300)
        assert written == target and target.read_text(encoding="utf-8").strip() == "ok"
        assert not [marker for marker in MARKERS if marker in _seen(api)]
    assert not home["flag"].exists() and _snapshot(home["home"]) == home["before"]


@pytest.mark.parametrize("agent_id", ["claude", "codex"])
def test_without_the_isolation_the_same_call_does_leak(home, agent_id, monkeypatch):
    """The control: pointing the CLI at the user's own config folder brings the planted instructions in."""
    own = {"claude": ("CLAUDE_CONFIG_DIR", home["home"] / ".claude"), "codex": ("CODEX_HOME", home["home"] / ".codex")}
    name, folder = own[agent_id]
    real_env = {"claude": commands.claude_env, "codex": commands.codex_env}[agent_id]

    def users_own(env, **kwargs):
        return {**real_env(env, **kwargs), name: str(folder)}

    monkeypatch.setattr(commands, f"{agent_id}_env", users_own)
    monkeypatch.setattr(contain, "prefix", lambda writable, *, temp: [])  # no file protection either
    if agent_id == "claude":  # --bare would still skip CLAUDE.md and hooks: take it out for the control
        real = commands.claude_command
        monkeypatch.setattr(commands, "claude_command",
                            lambda exe, **kwargs: [part for part in real(exe, **kwargs) if part != "--bare"])
    else:  # --ignore-user-config would still skip config.toml
        real = commands.codex_command

        def users_config(exe, **kwargs):
            command = [part for part in real(exe, **kwargs) if part != "--ignore-user-config"]
            at = command.index("project_doc_max_bytes=0")
            return command[:at - 1] + command[at + 1:]  # the setting and its 「-c」

        monkeypatch.setattr(commands, "codex_command", users_config)
    work = home["root"] / "work"
    work.mkdir()
    with fake_api.FakeModelApi() as api:
        runs.one_shot(_agent(agent_id, api), prompt="回复两个字：可用", model="fake-model", api_key=KEY,
                      thinking="medium", work_dir=work, config_root=home["root"] / "cfg", tools_root=TOOLS)
        assert [marker for marker in MARKERS if marker in _seen(api)]
