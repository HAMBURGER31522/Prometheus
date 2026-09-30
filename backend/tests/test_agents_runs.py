"""Running Codex CLI and Claude Code (PLAN 15.4.13): the answer read from their event streams, a
failure that says what the endpoint said (so the console names the reason), images, and workspace
tasks that get the same rules and skill text as Pi and must leave their file. The event streams are
real output of Claude Code 2.1.285 and Codex 0.159.0 against a local fake API (fixtures/agents)."""

import subprocess
from pathlib import Path

import pytest
from prometheus.agents import commands, runs
from prometheus.report import pi_run
from prometheus.tasks import errors

FIXTURES = Path(__file__).parent / "fixtures" / "agents"
CLAUDE = {"id": "claude", "access": "key", "base_url": "https://relay.example"}
CODEX = {"id": "codex", "access": "key", "base_url": "https://relay.example/v1"}


def _system(command: list) -> str:
    """The system text a run got: Claude Code's --append-system-prompt, Codex's developer_instructions."""
    if "--append-system-prompt" in command:
        return command[command.index("--append-system-prompt") + 1]
    import json

    found = [part for part in command if part.startswith("developer_instructions=")]
    return json.loads(found[0].split("=", 1)[1]) if found else ""


def _started(call) -> str:
    """The program behind the protection prefix (agents/contain.py)."""
    return call["command"][call["command"].index("--") + 1]


def _stream(name: str) -> bytes:
    return (FIXTURES / f"{name}.jsonl").read_bytes()


@pytest.fixture
def started(monkeypatch):
    """Every start of a CLI: its command, environment, folder and stdin; answers with `reply`."""
    calls = []
    reply = {"stdout": b"", "code": 0, "writes": None}

    def fake_run(command, *, input, capture_output, cwd, env, timeout=None, check=False):
        calls.append({"command": command, "env": env, "cwd": Path(cwd), "input": input.decode("utf-8"),
                      "timeout": timeout})
        if reply["writes"]:
            (Path(cwd) / reply["writes"]).write_text("<section>章</section>", encoding="utf-8")
        return subprocess.CompletedProcess(command, reply["code"], reply["stdout"], b"")

    monkeypatch.setattr(runs.subprocess, "run", fake_run)
    return calls, reply


def _one_shot(agent, tmp_path, **extra):
    return runs.one_shot(agent, prompt="回复两个字：可用", model="m", api_key="sk-x", thinking="medium",
                         work_dir=tmp_path / "work", config_root=tmp_path / "config", tools_root=tmp_path / "tools",
                         **{"files": [], **extra})


def test_claude_code_answers_from_its_result_event(started, tmp_path):
    calls, reply = started
    reply["stdout"] = _stream("claude-answer")
    (tmp_path / "work").mkdir()
    assert _one_shot(CLAUDE, tmp_path) == "可用" and len(calls) == 1
    call = calls[0]
    assert _started(call) == str(commands.executable(tmp_path / "tools", "claude"))
    assert call["input"] == "回复两个字：可用" and call["cwd"] == tmp_path / "work"
    assert call["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path / "config" / "claude")
    assert call["env"]["CLAUDE_CODE_MAX_RETRIES"] == "3"  # as Pi: three tries of its own before ours
    assert (tmp_path / "config" / "claude").is_dir()


def test_codex_answers_with_its_last_message(started, tmp_path):
    calls, reply = started
    reply["stdout"] = _stream("codex-answer")
    (tmp_path / "work").mkdir()
    assert _one_shot(CODEX, tmp_path) == "可用" and len(calls) == 1
    call = calls[0]
    assert _started(call) == str(commands.executable(tmp_path / "tools", "codex"))
    configs = [call["command"][i + 1] for i, part in enumerate(call["command"]) if part == "-c"]
    assert "model_providers.prometheus.request_max_retries=3" in configs
    assert "model_providers.prometheus.stream_max_retries=3" in configs
    assert call["env"]["CODEX_HOME"] == str(tmp_path / "config" / "codex") and (tmp_path / "config" / "codex").is_dir()


@pytest.mark.parametrize(("agent", "stream"), [(CLAUDE, "claude-rejected-key"), (CODEX, "codex-rejected-key")])
def test_a_rejected_key_is_reported_so_the_console_says_the_key_is_wrong(started, tmp_path, agent, stream):
    _calls, reply = started
    reply["stdout"], reply["code"] = _stream(stream), 1
    (tmp_path / "work").mkdir()
    with pytest.raises(runs.AgentRunError) as failure:
        _one_shot(agent, tmp_path)
    assert "401" in str(failure.value)
    assert errors.classify("report", str(failure.value), "EXTERNAL_MODEL_FAILURE") == "MODEL_KEY_INVALID"


def test_images_go_to_codex_as_attachments_and_claude_code_reads_them(started, tmp_path):
    calls, reply = started
    (tmp_path / "work").mkdir()
    frame = tmp_path / "work" / "frames" / "f_000030.jpg"
    reply["stdout"] = _stream("codex-answer")
    _one_shot(CODEX, tmp_path, files=[frame])
    assert len(calls) == 1
    command = calls[0]["command"]
    assert "--image" in command and command[command.index("--image") + 1] == str(frame)
    assert command.index("--image") < command.index("-")
    reply["stdout"] = _stream("claude-answer")
    _one_shot(CLAUDE, tmp_path, files=[frame])
    command = calls[1]["command"]
    assert command[command.index("--tools") + 1] == "Read"
    assert str(frame) in calls[1]["input"]


def _stage(workspace: Path) -> None:
    workspace.mkdir(parents=True)
    (workspace / "SKILL.md").write_text("技能正文：写报告的方法。", encoding="utf-8")


@pytest.mark.parametrize(("agent", "stream"), [(CLAUDE, "claude-answer"), (CODEX, "codex-answer")])
def test_a_task_gets_the_same_rules_and_skill_as_pi_and_leaves_its_file(started, tmp_path, agent, stream):
    calls, reply = started
    reply["stdout"], reply["writes"] = _stream(stream), "ch-01.html"
    workspace = tmp_path / "run"
    _stage(workspace)
    written = runs.task(agent, workspace, "写第 1 章", expect="ch-01.html", model="m", api_key="sk-x",
                        thinking="high", config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=600)
    assert written == workspace / "ch-01.html" and len(calls) == 1
    call = calls[0]
    assert "技能正文：写报告的方法。" in call["input"] and "写第 1 章" in call["input"]
    system = _system(call["command"])  # appended to the system prompt, as Pi's --append-system-prompt
    assert pi_run.SYSTEM in system and pi_run.SYSTEM not in call["input"]
    assert call["cwd"] == workspace and call["timeout"] == 600
    command = call["command"]
    if agent is CLAUDE:
        assert command[command.index("--tools") + 1] == "Read,Edit,PowerShell"
    else:
        assert command[command.index("--sandbox") + 1] == "danger-full-access"  # contained instead
    assert (workspace / "agent.events.jsonl").read_bytes() == _stream(stream)


def test_a_task_that_leaves_no_file_fails(started, tmp_path):
    _calls, reply = started
    reply["stdout"] = _stream("claude-answer")
    _stage(tmp_path / "run")
    with pytest.raises(runs.AgentRunError, match="ch-01.html"):
        runs.task(CLAUDE, tmp_path / "run", "写", expect="ch-01.html", model="m", api_key="k", thinking="medium",
                  config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=60)


def test_a_task_out_of_time_is_stopped_and_counts_as_a_timeout(monkeypatch, tmp_path):
    def slow(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    monkeypatch.setattr(runs.subprocess, "run", slow)
    _stage(tmp_path / "run")
    with pytest.raises(runs.AgentRunError) as failure:
        runs.task(CODEX, tmp_path / "run", "写", expect="x.html", model="m", api_key="k", thinking="medium",
                  config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=5)
    assert errors.classify("report", str(failure.value), "EXTERNAL_MODEL_FAILURE") == "MODEL_TIMEOUT"


def test_a_relay_failure_from_an_agent_is_tried_again(monkeypatch):
    from prometheus.report import workspace as workspace_mod

    monkeypatch.setattr(workspace_mod.time, "sleep", lambda seconds: None)
    tries = []

    def flaky():
        tries.append(1)
        if len(tries) == 1:
            raise runs.AgentRunError("Claude Code 调用失败：429 rate limited")
        return "ok"

    try:
        answer = workspace_mod._patient(flaky)
    except runs.AgentRunError:
        answer = None
    assert answer == "ok" and len(tries) == 2


def test_the_spend_counts_codex_and_claude_code_runs_too(tmp_path):
    """What rewrite.py prints (PLAN 15.4.13): Claude Code's result usage, Codex's turn usage (its input
    count includes the cached part), next to Pi's own events."""
    from prometheus.report import evaluation

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "agent.events.jsonl").write_text(
        '{"type":"result","subtype":"success","is_error":false,"num_turns":4,'
        '"usage":{"input_tokens":1000,"output_tokens":200,"cache_read_input_tokens":5000,'
        '"cache_creation_input_tokens":300}}\n', encoding="utf-8")
    (tmp_path / "b" / "agent.events.jsonl").write_text(
        '{"type":"turn.completed","usage":{"input_tokens":9000,"cached_input_tokens":6000,"output_tokens":700,'
        '"reasoning_output_tokens":400}}\n', encoding="utf-8")
    total = evaluation.pi_usage(tmp_path)
    assert (total["input"], total["cacheRead"], total["output"], total["cacheWrite"]) == (1000 + 3000, 5000 + 6000,
                                                                                          200 + 700, 300)
    assert total["replies"] == 4 + 1
    later = evaluation.pi_events_offsets(tmp_path)
    assert evaluation.pi_usage(tmp_path, later)["input"] == 0


@pytest.mark.parametrize(("agent", "stream"), [(CLAUDE, "claude-answer"), (CODEX, "codex-answer")])
def test_a_task_gets_the_python_the_skill_tells_the_model_about(started, tmp_path, agent, stream):
    """modes/standard.md: 「Pi 运行环境提供 VIDEO_REPORT_PYTHON，可用 "$VIDEO_REPORT_PYTHON" draw.py」 — as Pi's runs get it."""
    import sys

    calls, reply = started
    reply["stdout"], reply["writes"] = _stream(stream), "ch-01.html"
    _stage(tmp_path / "run")
    runs.task(agent, tmp_path / "run", "写", expect="ch-01.html", model="m", api_key="k", thinking="medium",
              config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=60)
    assert calls and calls[0]["env"].get("VIDEO_REPORT_PYTHON") == sys.executable
    assert calls[0]["env"].get("PYTHONUTF8") == "1"


def test_without_the_profiles_numbers_the_models_own_limits_apply_as_for_pi(started, tmp_path, monkeypatch):
    """Pi fills an empty 「高级」 from the model catalogue (claude-opus-4-8: 1M); Claude Code would
    otherwise fall back to 200k for a Claude model without 「[1m]」, Codex to its own guess."""
    from prometheus.llm import pi_models

    calls, reply = started
    (tmp_path / "work").mkdir()
    looked = []
    monkeypatch.setattr(pi_models, "model_fields",
                        lambda data_dir, profile, pi_cli=None: looked.append(profile) or
                        ("pi", {"contextWindow": 1000000, "maxTokens": 128000}))
    reply["stdout"] = _stream("claude-answer")
    runs.one_shot({**CLAUDE, "protocol": "anthropic"}, prompt="你好", model="claude-opus-4-8", api_key="k",
                  thinking="medium", work_dir=tmp_path / "work", config_root=tmp_path / "data" / ".prometheus" / "config",
                  tools_root=tmp_path / "tools")
    command = calls[0]["command"]
    assert command[command.index("--model") + 1] == "claude-opus-4-8[1m]"
    assert calls[0]["env"].get("CLAUDE_CODE_MAX_OUTPUT_TOKENS") == "128000"
    assert looked and looked[0]["model"] == "claude-opus-4-8"
    reply["stdout"] = _stream("codex-answer")
    runs.one_shot({**CODEX, "protocol": "openai"}, prompt="你好", model="gpt-6-astra", api_key="k", thinking="medium",
                  work_dir=tmp_path / "work", config_root=tmp_path / "data" / ".prometheus" / "config",
                  tools_root=tmp_path / "tools")
    assert "model_context_window=1000000" in [calls[1]["command"][i + 1] for i, part in enumerate(calls[1]["command"])
                                               if part == "-c"]


def test_a_name_no_catalogue_knows_runs_1m_when_the_profile_says_so(started, tmp_path, monkeypatch):
    """The settings hint (user 2026-09-30): 「如果它是 1M 的，在这里填 1000000，应用会自动加上「[1m]」」."""
    from prometheus.llm import pi_models

    calls, reply = started
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(pi_models, "model_fields", lambda data_dir, profile, pi_cli=None: (None, {}))
    reply["stdout"] = _stream("claude-answer")
    runs.one_shot({**CLAUDE, "protocol": "anthropic", "context_window": 1000000}, prompt="你好",
                  model="relay-opus-thinking", api_key="k", thinking="medium", work_dir=tmp_path / "work",
                  config_root=tmp_path / "data" / ".prometheus" / "config", tools_root=tmp_path / "tools")
    command = calls[0]["command"]
    assert command[command.index("--model") + 1] == "relay-opus-thinking[1m]"
    assert calls[0]["env"].get("CLAUDE_CODE_MAX_CONTEXT_TOKENS") == "1000000"
    reply["stdout"] = _stream("claude-answer")
    runs.one_shot({**CLAUDE, "protocol": "anthropic"}, prompt="你好", model="relay-opus-thinking", api_key="k",
                  thinking="medium", work_dir=tmp_path / "work",
                  config_root=tmp_path / "data" / ".prometheus" / "config", tools_root=tmp_path / "tools")
    assert calls[1]["command"][calls[1]["command"].index("--model") + 1] == "relay-opus-thinking"  # left empty: 200k


@pytest.mark.parametrize(("agent", "stream", "names"), [
    (CLAUDE, "claude-answer", ("Read", "Edit", "UTF-8")),
    (CODEX, "codex-answer", ("view_image", "apply_patch", "UTF-8")),
])
def test_a_task_is_told_which_of_its_tools_are_pis_read_write_edit_and_powershell(started, tmp_path, agent, stream, names):
    """The rules and figures.md say 「用 read 工具查看候选帧」「写回整章」 in Pi's words; Codex looks at
    images with view_image and Claude Code has no Write, and PowerShell 5.1 reads UTF-8 as GBK."""
    calls, reply = started
    reply["stdout"], reply["writes"] = _stream(stream), "ch-01.html"
    _stage(tmp_path / "run")
    runs.task(agent, tmp_path / "run", "写", expect="ch-01.html", model="m", api_key="k", thinking="medium",
              config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=60)
    assert calls
    system = _system(calls[0]["command"])
    for name in names:
        assert name in system


def test_the_skill_goes_once_when_the_prompt_already_carries_it(started, tmp_path):
    calls, reply = started
    reply["stdout"], reply["writes"] = _stream("claude-answer"), "ch-01.html"
    _stage(tmp_path / "run")
    prompt = "写第 1 章\n\n=== 附件：SKILL.md ===\n技能正文：写报告的方法。"
    runs.task(CLAUDE, tmp_path / "run", prompt, expect="ch-01.html", model="m", api_key="k", thinking="medium",
              config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=60)
    assert calls and calls[0]["input"].count("技能正文：写报告的方法。") == 1
