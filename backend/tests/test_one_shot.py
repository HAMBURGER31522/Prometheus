"""One-shot text calls: prompt via stdin, full --no-* flag set (PLAN 8.6)."""

import json
import sys
from pathlib import Path

from prometheus.report.one_shot import ONE_SHOT_FLAGS, run_one_shot

LONG_PROMPT = "讲解要点。" * 2000  # > 9000 chars


def make_fake_pi_cmd(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_pi_script.py"
    script.write_text(body, encoding="utf-8")
    launcher = tmp_path / "fake-pi.cmd"
    launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    return launcher


FAKE = """#!/usr/bin/env python3
import json, sys
open("argv.json", "w", encoding="utf-8").write(json.dumps(sys.argv[1:]))
open("stdin.txt", "wb").write(sys.stdin.buffer.read())
print("分类结果文本")
"""


def test_long_prompt_travels_via_stdin(tmp_path):
    executable = make_fake_pi_cmd(tmp_path, FAKE)
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    out = run_one_shot(
        tmp_path, prompt=LONG_PROMPT, provider="deepseek", model="deepseek-flash",
        api_key="sk-x", thinking="low", node_exe="node.exe", pi_cli=str(executable),
        agent_dir=agent_dir,
    )
    assert out == "分类结果文本"
    argv = json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))
    assert LONG_PROMPT not in " ".join(argv)
    stdin_text = (tmp_path / "stdin.txt").read_text(encoding="utf-8")
    assert stdin_text == LONG_PROMPT


def test_command_carries_all_no_flags_and_model_args(tmp_path):
    executable = make_fake_pi_cmd(tmp_path, FAKE)
    run_one_shot(
        tmp_path, prompt="短提示", provider="zhipu", model="glm-5.3-flash",
        api_key="sk-y", thinking="high", node_exe="node.exe", pi_cli=str(executable),
        agent_dir=tmp_path / "agent2",
    )
    argv = json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))
    for flag in ONE_SHOT_FLAGS:
        assert flag in argv
    assert argv[argv.index("--provider") + 1] == "zhipu"
    assert argv[argv.index("--model") + 1] == "glm-5.3-flash"
    assert argv[argv.index("--thinking") + 1] == "high"
    assert argv[argv.index("--api-key") + 1] == "sk-y"
