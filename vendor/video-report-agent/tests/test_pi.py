"""Protocol failure tests, not evidence of a real model run."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from video_report_agent.pi import (
    PI_AGENT_DIR,
    PiError,
    PiRunner,
)

FAKE_PI_SETUP = (
    "import json, os, sys\n"
    "sys.stdin.reconfigure(encoding='utf-8')\n"
    "sys.stdout.reconfigure(encoding='utf-8')\n"
)


def make_fake_pi(tmp_path: Path, body: str) -> Path:
    """Runnable stand-in for the pi CLI: a script file plus a native launcher.

    Windows cannot exec a shebang script (WinError 193), so there the launcher
    is a .cmd that runs the same script with the current interpreter.
    """
    lines = body.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        body = "".join(lines[1:])
    script = tmp_path / "fake_pi_script.py"
    script.write_text(FAKE_PI_SETUP + body, encoding="utf-8")
    if sys.platform == "win32":
        launcher = tmp_path / "fake-pi.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        return launcher
    executable = tmp_path / "fake-pi"
    executable.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    executable.chmod(0o755)
    return executable


class Input:
    def write(self, data):
        assert json.loads(data)["type"] == "prompt"

    async def drain(self):
        pass


class Process:
    def __init__(self, events):
        self.stdin = Input()
        self.stdout = self
        self.lines = []
        for event in events:
            self.lines.append((json.dumps(event) + "\n").encode())

    async def readline(self):
        return self.lines.pop(0) if self.lines else b""


def test_default_thinking_is_low():
    assert PiRunner().thinking == "low"
    assert PiRunner(thinking="high").thinking == "high"


def test_review_is_opt_in_and_evaluation_can_override(monkeypatch):
    monkeypatch.delenv("REPORT_REVIEW", raising=False)
    assert PiRunner().review is False
    monkeypatch.setenv("REPORT_REVIEW", "1")
    assert PiRunner().review is True
    assert PiRunner(review=False).review is False


def test_agent_end_is_not_success(tmp_path):
    with pytest.raises(PiError, match="before agent_settled"):
        asyncio.run(PiRunner()._consume(Process([{"type": "agent_end"}]), tmp_path, "task"))


def test_failed_final_message_is_not_success(tmp_path):
    events = [
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "stopReason": "error",
                "errorMessage": "quota exceeded",
            },
        },
        {"type": "agent_settled"},
    ]
    with pytest.raises(PiError, match="quota exceeded") as error:
        asyncio.run(PiRunner()._consume(Process(events), tmp_path, "task"))
    assert error.value.category == "EXTERNAL_MODEL_FAILURE"


def test_settled_after_retry_uses_final_message(tmp_path):
    events = [
        {"type": "message_end", "message": {"role": "assistant", "stopReason": "error"}},
        {"type": "agent_end", "willRetry": True},
        {"type": "message_end", "message": {"role": "assistant", "stopReason": "stop"}},
        {"type": "agent_settled"},
    ]
    asyncio.run(PiRunner()._consume(Process(events), tmp_path, "task"))
    events_text = (tmp_path / "pi.events.jsonl").read_text(encoding="utf-8")
    recorded = [json.loads(line) for line in events_text.splitlines()]
    assert len(recorded) == 4
    assert all(isinstance(event.pop("_trace_received_at"), float) for event in recorded)
    assert recorded == events


def test_rejected_prompt(tmp_path):
    with pytest.raises(PiError, match="unknown model"):
        asyncio.run(
            PiRunner()._consume(
                Process([{"type": "response", "success": False, "error": "unknown model"}]),
                tmp_path,
                "task",
            )
        )


def test_missing_output_and_run_cwd(tmp_path, monkeypatch):
    executable = make_fake_pi(tmp_path, """#!/usr/bin/env python3
import json,sys,os
json.loads(sys.stdin.readline())
assert os.path.isfile("transcript.md")
assert os.path.isfile("SKILL.md")
assert os.path.isfile("assets/report-template.html")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}),flush=True)
""")
    monkeypatch.setattr("video_report_agent.pi.shutil.which", lambda _: str(executable))
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "transcript.md").write_text("sample", encoding="utf-8")
    with pytest.raises(PiError, match="without report.html"):
        asyncio.run(PiRunner(review=True).run(workspace))
    invocation = json.loads((workspace / "invocation.json").read_text(encoding="utf-8"))
    assert Path(invocation["cwd"]) == workspace
    assert "read,write,edit,bash,inspect_report" in invocation["command"]
    assert "--extension" in invocation["command"]
    assert "{{VIDEO_DESCRIPTION}}" in invocation["prompt"]
    assert "不要读取、改写或自行生成视频简介" in invocation["prompt"]
    assert "蓝色或黄色背景" not in invocation["prompt"]


def test_project_provider_model_and_api_key_are_passed_but_redacted(tmp_path, monkeypatch):
    executable = make_fake_pi(tmp_path, """#!/usr/bin/env python3
import json,sys,os
open("received-argv.json", "w").write(json.dumps(sys.argv[1:]))
open("received-agent-dir.txt", "w").write(os.environ["PI_CODING_AGENT_DIR"])
json.loads(sys.stdin.readline())
open("report.html", "w").write("<html><body>ok</body></html>")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}),flush=True)
""")
    monkeypatch.setattr("video_report_agent.pi.shutil.which", lambda _: str(executable))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "machine-pi"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PI_PROVIDER", "openai")
    monkeypatch.setenv("PI_MODEL", "gpt-test")
    monkeypatch.setenv("PI_API_KEY", "project-secret")
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "transcript.md").write_text("sample", encoding="utf-8")

    asyncio.run(PiRunner(thinking="high").run(workspace))

    assert Path((workspace / "received-agent-dir.txt").read_text(encoding="utf-8")) == PI_AGENT_DIR
    assert PI_AGENT_DIR.is_absolute()
    received = json.loads((workspace / "received-argv.json").read_text(encoding="utf-8"))
    assert received[received.index("--thinking") + 1] == "high"
    assert received[received.index("--provider") + 1] == "openai"
    assert received[received.index("--model") + 1] == "gpt-test"
    assert received[received.index("--api-key") + 1] == "project-secret"
    invocation = json.loads((workspace / "invocation.json").read_text(encoding="utf-8"))
    assert "project-secret" not in json.dumps(invocation)
    assert invocation["command"][invocation["command"].index("--api-key") + 1] == "[redacted]"


def test_empty_project_api_key_allows_project_login(monkeypatch):
    monkeypatch.setenv("PI_PROVIDER", "deepseek")
    monkeypatch.setenv("PI_MODEL", "deepseek-chat")
    monkeypatch.setenv("PI_API_KEY", "   ")

    runner = PiRunner()

    assert runner.provider == "deepseek"
    assert runner.model == "deepseek-chat"
    assert runner.api_key is None


def test_env_key_is_not_sent_to_another_provider(monkeypatch):
    monkeypatch.setenv("PI_PROVIDER", "deepseek")
    monkeypatch.setenv("PI_API_KEY", "deepseek-secret")
    assert PiRunner(provider="custom-other", model="test").api_key is None


def test_selected_provider_saved_key_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr("video_report_agent.pi.PI_AGENT_DIR", tmp_path)
    (tmp_path / "auth.json").write_text(json.dumps({
        "deepseek": {"type": "api_key", "key": "new-key"},
    }), encoding="utf-8")
    monkeypatch.setenv("PI_PROVIDER", "deepseek")
    monkeypatch.setenv("PI_API_KEY", "old-key")
    assert PiRunner(provider="deepseek", model="test").api_key is None


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("report_mode", ["standard", "brief"])
def test_custom_skill_directory(tmp_path, monkeypatch, explicit, report_mode):
    custom = tmp_path / "custom"
    (custom / "assets").mkdir(parents=True)
    (custom / "SKILL.md").write_text("custom skill marker", encoding="utf-8")
    (custom / "assets/report-template.html").write_text("custom template marker", encoding="utf-8")
    executable = make_fake_pi(tmp_path, """#!/usr/bin/env python3
import json, sys
assert open("SKILL.md").read() == "custom skill marker"
assert open("assets/report-template.html").read() == "custom template marker"
json.loads(sys.stdin.readline())
open("report.html", "w").write("<html><body>fixture</body></html>")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}), flush=True)
""")
    monkeypatch.setattr("video_report_agent.pi.shutil.which", lambda _: str(executable))
    monkeypatch.setattr("video_report_agent.pi.PI_AGENT_DIR", tmp_path / "config")
    monkeypatch.setenv("VIDEO_REPORT_SKILL_DIR", str(tmp_path / "wrong" if explicit else custom))
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "transcript.md").write_text("fixture", encoding="utf-8")
    mode_payload = json.dumps({"report_mode": report_mode})
    (workspace / "input.json").write_text(mode_payload, encoding="utf-8")
    runner = PiRunner(skill_dir=custom if explicit else None)
    assert asyncio.run(runner.run(workspace)) == workspace / "report.html"
    assert (tmp_path / "config/models.json").is_file()
