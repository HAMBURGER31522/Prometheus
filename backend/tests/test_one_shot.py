"""One-shot text calls: prompt via stdin, full --no-* flag set (PLAN 8.6)."""

import json
from pathlib import Path

import pytest
from prometheus.llm.one_shot import ONE_SHOT_FLAGS, OneShotError, run_one_shot

LONG_PROMPT = "讲解要点。" * 2000  # > 9000 chars


# Pi runs contained (PLAN 15.4.13): its own folder is the one place it may write.
FAKE_JS = """const fs = require("fs");
const own = process.env.PI_CODING_AGENT_DIR;
fs.writeFileSync(own + "/argv.json", JSON.stringify(process.argv.slice(2)));
fs.writeFileSync(own + "/stdin.txt", fs.readFileSync(0, "utf8"));
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
    argv = json.loads((agent_dir / "argv.json").read_text(encoding="utf-8"))
    assert LONG_PROMPT not in " ".join(argv)
    stdin_text = (agent_dir / "stdin.txt").read_text(encoding="utf-8")
    assert stdin_text == LONG_PROMPT


def test_command_carries_all_no_flags_and_model_args(tmp_path):
    executable = make_fake_pi_js(tmp_path)
    run_one_shot(
        tmp_path, prompt="短提示", provider="zhipu", model="glm-5.3-flash",
        api_key="sk-y", thinking="high", node_exe="node.exe", pi_cli=str(executable),
        agent_dir=tmp_path / "agent2",
    )
    argv = json.loads((tmp_path / "agent2" / "argv.json").read_text(encoding="utf-8"))
    for flag in ONE_SHOT_FLAGS:
        assert flag in argv
    assert argv[argv.index("--provider") + 1] == "zhipu"
    assert argv[argv.index("--model") + 1] == "glm-5.3-flash"
    assert argv[argv.index("--thinking") + 1] == "high"
    assert argv[argv.index("--api-key") + 1] == "sk-y"


def test_images_ride_along_as_at_files_after_the_options(tmp_path):
    """Pi's `pi -p @screenshot.png "What's in this image?"` (README, File Arguments): the frame ledger."""
    executable = make_fake_pi_js(tmp_path)
    frames = [tmp_path / "f_000030.jpg", tmp_path / "f_000400.jpg"]
    for frame in frames:
        frame.write_bytes(b"jpg")
    run_one_shot(
        tmp_path, prompt="看图", provider="custom", model="m", api_key="sk-z", thinking="medium",
        node_exe="node.exe", pi_cli=str(executable), agent_dir=tmp_path / "agent3", files=frames,
    )
    argv = json.loads((tmp_path / "agent3" / "argv.json").read_text(encoding="utf-8"))
    assert argv[-2:] == [f"@{frames[0]}", f"@{frames[1]}"]
    assert (tmp_path / "agent3" / "stdin.txt").read_text(encoding="utf-8") == "看图"


# Pi's print mode writes the provider's error message to stderr and exits 1 (dist/modes/print-mode.js).
FAILING_JS = """const body = JSON.stringify({message: "You exceeded your current quota. " + "x".repeat(400),
  type: "insufficient_quota", param: null, code: "insufficient_quota"});
console.error("429: " + body);
process.exit(1);
"""


def test_a_failed_call_keeps_the_whole_error_text(tmp_path):
    # The console's 「详情」 shows the original error in full (PLAN 15.4.10), so nothing is cut.
    script = tmp_path / "failing-pi-cli.js"
    script.write_text(FAILING_JS, encoding="utf-8")
    with pytest.raises(OneShotError) as caught:
        run_one_shot(
            tmp_path, prompt="短提示", provider="openai", model="gpt-x", api_key="sk-z",
            thinking="low", node_exe="node.exe", pi_cli=str(script), agent_dir=tmp_path / "agent3",
        )
    message = str(caught.value)
    assert message.startswith("一次性文本调用失败（exit 1）：429: {")
    assert message.rstrip().endswith('"code":"insufficient_quota"}')
    assert "x" * 400 in message
