"""One-shot text calls: prompt via stdin, full --no-* flag set (PLAN 8.6)."""

import json
from pathlib import Path

from prometheus.report.one_shot import ONE_SHOT_FLAGS, run_one_shot

LONG_PROMPT = "讲解要点。" * 2000  # > 9000 chars


FAKE_JS = """const fs = require("fs");
fs.writeFileSync("argv.json", JSON.stringify(process.argv.slice(2)));
fs.writeFileSync("stdin.txt", fs.readFileSync(0, "utf8"));
console.log("分类结果文本");
"""


def make_fake_pi_js(tmp_path: Path) -> Path:
    script = tmp_path / "fake-pi-cli.js"
    script.write_text(FAKE_JS, encoding="utf-8")
    return script


def test_long_prompt_travels_via_stdin(tmp_path):
    executable = make_fake_pi_js(tmp_path)
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
    executable = make_fake_pi_js(tmp_path)
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
