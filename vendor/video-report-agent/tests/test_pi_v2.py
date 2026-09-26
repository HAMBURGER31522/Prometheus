"""V2 acceptance: agent_dir, command_prefix, tools, extra_prompt, extra_files."""

import asyncio
import json
from pathlib import Path

import pytest

from test_pi import make_fake_pi

import video_report_agent.pi as pi_mod
from video_report_agent.pi import PiError, PiRunner

SETTLE = """#!/usr/bin/env python3
import json,sys,os
open("received-argv.json", "w").write(json.dumps(sys.argv[1:]))
open("received-agent-dir.txt", "w").write(os.environ["PI_CODING_AGENT_DIR"])
json.loads(sys.stdin.readline())
open("report.html", "w").write("<html><body>ok</body></html>")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}),flush=True)
"""

FAIL = "#!/usr/bin/env python3\nimport sys; sys.exit(3)\n"


def _run(tmp_path, monkeypatch, *, settle=True, **kwargs):
    executable = make_fake_pi(tmp_path, SETTLE if settle else FAIL)
    if "command_prefix" not in kwargs:
        monkeypatch.setattr(pi_mod.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(pi_mod, "PI_AGENT_DIR", tmp_path / "module-config")
    workspace = tmp_path / "run"
    workspace.mkdir(exist_ok=True)
    (workspace / "transcript.md").write_text("sample", encoding="utf-8")
    try:
        asyncio.run(PiRunner(**kwargs).run(workspace))
    except PiError:
        if settle:
            raise
    invocation = json.loads((workspace / "invocation.json").read_text(encoding="utf-8"))
    return invocation, workspace


def test_agent_dir_overrides_module_level_discovery(tmp_path, monkeypatch):
    agent_dir = tmp_path / "agent"
    invocation, _workspace = _run(tmp_path, monkeypatch, agent_dir=agent_dir)
    assert (agent_dir / "models.json").is_file()
    received = (tmp_path / "run" / "received-agent-dir.txt").read_text(encoding="utf-8")
    assert received == str(agent_dir)
    assert "--session-dir" in invocation["command"]


def test_command_prefix_replaces_shutil_which(tmp_path, monkeypatch):
    def fail(_):
        raise AssertionError("shutil.which must not be called with command_prefix")

    monkeypatch.setattr(pi_mod.shutil, "which", fail)
    invocation, _workspace = _run(
        tmp_path, monkeypatch, settle=False, command_prefix=["node", "cli.js"],
    )
    assert invocation["command"][:2] == ["node", "cli.js"]


def test_tools_parameter_replaces_default(tmp_path, monkeypatch):
    invocation, _workspace = _run(
        tmp_path, monkeypatch, tools="read,write,edit,powershell",
    )
    command = invocation["command"]
    assert command[command.index("--tools") + 1] == "read,write,edit,powershell"

    default_invocation, _workspace = _run(tmp_path, monkeypatch)
    default_command = default_invocation["command"]
    assert default_command[default_command.index("--tools") + 1] == "read,write,edit,bash"


def test_extra_prompt_appended_to_user_prompt(tmp_path, monkeypatch):
    invocation, _workspace = _run(
        tmp_path, monkeypatch, extra_prompt="本机为 Windows，命令工具是 PowerShell。",
    )
    assert invocation["prompt"].endswith("本机为 Windows，命令工具是 PowerShell。")


def test_extra_files_copied_into_workspace(tmp_path, monkeypatch):
    overlay = tmp_path / "overlay.md"
    overlay.write_text("配图规则", encoding="utf-8")
    _invocation, workspace = _run(tmp_path, monkeypatch, extra_files=[overlay])
    assert (workspace / "overlay.md").read_text(encoding="utf-8") == "配图规则"
