"""V2 baseline: default-arg command generation must not change (appendix A V2)."""

import asyncio
import json
from pathlib import Path

from test_pi import make_fake_pi

import video_report_agent.pi as pi_mod
from video_report_agent.pi import PiRunner

FIXTURE = Path(__file__).parent / "fixtures" / "pi-command-baseline.json"

BODY = """#!/usr/bin/env python3
import json,sys,os
open("received-argv.json", "w").write(json.dumps(sys.argv[1:]))
open("received-agent-dir.txt", "w").write(os.environ["PI_CODING_AGENT_DIR"])
json.loads(sys.stdin.readline())
open("report.html", "w").write("<html><body>ok</body></html>")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}),flush=True)
"""


def _normalize(value, tmp_path):
    if isinstance(value, str):
        return value.replace(str(tmp_path), "<TMP>")
    if isinstance(value, list):
        return [_normalize(item, tmp_path) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item, tmp_path) for key, item in value.items()}
    return value


def test_default_command_matches_pre_v2_baseline(tmp_path, monkeypatch):
    executable = make_fake_pi(tmp_path, BODY)
    monkeypatch.setattr(pi_mod.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(pi_mod, "PI_AGENT_DIR", tmp_path / "config")
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "transcript.md").write_text("sample", encoding="utf-8")

    asyncio.run(PiRunner().run(workspace))

    invocation = json.loads((workspace / "invocation.json").read_text(encoding="utf-8"))
    baseline = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert _normalize(invocation, tmp_path) == baseline
