"""Our own Pi runs for 完整精读 (PLAN 15.4.11): planning and one run per chapter. Same flags as
vendor's PiRunner, our prompt, and the file each run must leave behind."""

import json
import sys
from pathlib import Path

import pytest
from prometheus.report import pi_run

FAKE_PI = """import json, os, sys
open("argv.json", "w", encoding="utf-8").write(json.dumps(sys.argv[1:]))
message = json.loads(sys.stdin.readline())
open("prompt.txt", "w", encoding="utf-8").write(message["message"])
stop = os.environ.get("FAKE_STOP", "stop")
if os.environ.get("FAKE_WRITE", "1") == "1":
    open("out.html", "w", encoding="utf-8").write("<section>第一章</section>")
print(json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": stop,
                                                     "errorMessage": "模型输出被截断"}}))
print(json.dumps({"type": "agent_settled"}), flush=True)
"""

LLM = {"provider": "custom", "model": "claude-opus-4-8", "api_key": "sk-test", "thinking": "medium"}


@pytest.fixture
def fake_pi(tmp_path):
    script = tmp_path / "fake_pi.py"
    script.write_text(FAKE_PI, encoding="utf-8")
    return [sys.executable, str(script)]


def test_the_command_has_vendors_flags_our_tools_and_no_report_html_promise(tmp_path):
    command = pi_run.pi_command(["node.exe", "cli.js"], tmp_path, LLM)
    assert command[:3] == ["node.exe", "cli.js", "--mode"]
    for flag in ("--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files",
                 "--offline"):
        assert flag in command
    assert command[command.index("--tools") + 1] == "read,write,edit,powershell"
    assert command[command.index("--skill") + 1] == str(tmp_path / "SKILL.md")
    assert command[command.index("--session-dir") + 1] == str(tmp_path / "sessions")
    assert command[command.index("--thinking") + 1] == "medium"
    assert command[command.index("--api-key") + 1] == "sk-test"
    system = command[command.index("--append-system-prompt") + 1]
    assert "Work only inside this run workspace" in system and "report.html" not in system


def test_a_run_sends_our_prompt_and_returns_the_file_it_must_leave(tmp_path, fake_pi, monkeypatch):
    monkeypatch.setattr(pi_run, "pi_command", lambda prefix, workspace, llm, **kw: [*fake_pi])
    out = pi_run.run_task(tmp_path, "只写第一章，写入 out.html。", expect="out.html", llm=LLM,
                          prefix=fake_pi, agent_dir=tmp_path / "agent", timeout=60)
    assert out == tmp_path / "out.html"
    assert (tmp_path / "prompt.txt").is_file()
    assert (tmp_path / "prompt.txt").read_text(encoding="utf-8") == "只写第一章，写入 out.html。"
    assert (tmp_path / "pi.events.jsonl").is_file()


def test_a_run_that_does_not_stop_normally_or_leaves_nothing_fails_with_the_reason(tmp_path, fake_pi, monkeypatch):
    monkeypatch.setattr(pi_run, "pi_command", lambda prefix, workspace, llm, **kw: [*fake_pi])
    monkeypatch.setenv("FAKE_STOP", "length")
    with pytest.raises(pi_run.PiRunError, match="截断"):
        pi_run.run_task(tmp_path, "写", expect="out.html", llm=LLM, prefix=fake_pi, agent_dir=tmp_path, timeout=60)
    monkeypatch.setenv("FAKE_STOP", "stop")
    monkeypatch.setenv("FAKE_WRITE", "0")
    (tmp_path / "out.html").unlink(missing_ok=True)
    with pytest.raises(pi_run.PiRunError, match="out.html"):
        pi_run.run_task(tmp_path, "写", expect="out.html", llm=LLM, prefix=fake_pi, agent_dir=tmp_path, timeout=60)


def test_the_skill_is_staged_for_standard_only(tmp_path):
    pi_run.stage_skill(tmp_path)
    assert (tmp_path / "SKILL.md").is_file()
    assert (tmp_path / "modes" / "standard.md").is_file()
    assert (tmp_path / "assets" / "report-template.html").is_file()
    assert not (tmp_path / "modes" / "brief.md").exists()
    assert not (tmp_path / "assets" / "brief-report-template.html").exists()
    assert json.loads(json.dumps(sorted(p.name for p in (tmp_path / "references").iterdir())))
    assert Path(pi_run.SKILL_DIR).name == "video-report"
