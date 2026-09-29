"""How the app starts its own Codex CLI and Claude Code (PLAN 15.4.13): the private copies, their own
config folders, the switches that keep the user's plugins, hooks, instructions and history out, the
thinking levels; the key only in the child's environment, never on its command line."""

from pathlib import Path

from prometheus.agents import commands

TOOLS = Path("E:/tools/P")
CONFIG = Path("D:/data/.prometheus/config")
PARENT = {"PATH": "p", "TEMP": "t", "CLAUDE_CODE_SESSION_ID": "s", "CLAUDECODE": "1", "ANTHROPIC_BASE_URL": "u",
          "OPENAI_API_KEY": "k", "CODEX_HOME": "h", "CLAUDE_CONFIG_DIR": "c"}


def _value(command, flag):
    return command[command.index(flag) + 1]


def _configs(command):
    return [command[i + 1] for i, part in enumerate(command) if part == "-c"]


def test_the_private_copies_live_under_the_tools_folder():
    assert commands.executable(TOOLS, "claude") == (
        TOOLS / "agents/claude/node_modules/@anthropic-ai/claude-code/bin/claude.exe")
    assert commands.executable(TOOLS, "codex") == (
        TOOLS / "agents/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe")


def test_variables_inherited_from_another_agent_are_dropped():
    assert commands.clean_env(PARENT) == {"PATH": "p", "TEMP": "t"}


def test_claude_code_runs_bare_in_its_own_folder_with_the_key_only_in_its_environment():
    command = commands.claude_command(Path("claude.exe"), model="gpt-6-astra-cc-format[1m]", thinking="high", tools=False)
    for flag in ("-p", "--bare", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in command
    assert _value(command, "--output-format") == "stream-json" and "--verbose" in command
    assert _value(command, "--model") == "gpt-6-astra-cc-format[1m]"
    assert _value(command, "--effort") == "high"
    assert _value(command, "--tools") == ""
    env = commands.claude_env(PARENT, config_root=CONFIG, base_url="https://relay.example", api_key="sk-x")
    assert env["CLAUDE_CONFIG_DIR"] == str(CONFIG / "claude")
    assert (env["ANTHROPIC_BASE_URL"], env["ANTHROPIC_API_KEY"]) == ("https://relay.example", "sk-x")
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1" and env["DISABLE_AUTOUPDATER"] == "1"
    assert "CLAUDE_CODE_SESSION_ID" not in env and "CLAUDECODE" not in env and env["PATH"] == "p"


def test_claude_code_works_with_read_edit_and_powershell_and_never_asks():
    command = commands.claude_command(Path("claude.exe"), model="m", thinking="medium", tools=True)
    assert "--permission-mode" in command and _value(command, "--permission-mode") == "dontAsk"
    assert _value(command, "--tools") == "Read,Edit,PowerShell"
    assert _value(command, "--allowedTools") == "Read,Edit,PowerShell"


def test_claude_code_has_no_off_so_off_becomes_low():
    command = commands.claude_command(Path("claude.exe"), model="m", thinking="off", tools=False)
    assert "--effort" in command and _value(command, "--effort") == "low"


def test_codex_talks_to_the_endpoint_as_its_own_provider_with_its_extras_off():
    command = commands.codex_command(Path("codex.exe"), model="gpt-6-astra", thinking="xhigh",
                                     workspace=Path("W:/run"), write=False, base_url="https://relay.example/v1")
    for flag in ("exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"):
        assert flag in command
    configs = _configs(command)
    assert 'model_provider="prometheus"' in configs
    assert 'model_providers.prometheus.base_url="https://relay.example/v1"' in configs
    assert 'model_providers.prometheus.wire_api="responses"' in configs
    assert 'model_providers.prometheus.env_key="PROMETHEUS_AGENT_KEY"' in configs
    for setting in ('model_reasoning_effort="xhigh"', "project_doc_max_bytes=0", "skills.include_instructions=false",
                    'web_search="disabled"', "check_for_update_on_startup=false"):
        assert setting in configs
    disabled = {command[i + 1] for i, part in enumerate(command) if part == "--disable"}
    assert {"plugins", "remote_plugin", "apps", "browser_use", "computer_use", "goals", "hooks", "image_generation",
            "multi_agent", "skill_search", "tool_suggest"} <= disabled
    # on by default: an endpoint that cannot be reached is tried forever, and the call never ends
    assert "unbounded_connection_retries" in disabled
    assert _value(command, "--sandbox") == "read-only" and _value(command, "-C") == str(Path("W:/run"))
    assert _value(command, "--model") == "gpt-6-astra" and command[-1] == "-"
    env = commands.codex_env(PARENT, config_root=CONFIG, api_key="sk-x")
    assert env["CODEX_HOME"] == str(CONFIG / "codex") and env["PROMETHEUS_AGENT_KEY"] == "sk-x"
    assert "OPENAI_API_KEY" not in env and "CLAUDE_CODE_SESSION_ID" not in env


def test_codex_tasks_write_without_its_own_sandbox_and_off_is_none():
    """Its Windows sandbox refuses every command without a window; the run is protected by
    agents/contain.py instead (user 2026-09-29)."""
    command = commands.codex_command(Path("codex.exe"), model="m", thinking="off", workspace=Path("W:/run"),
                                     write=True, base_url="https://relay.example/v1")
    assert "--sandbox" in command and _value(command, "--sandbox") == "danger-full-access"
    assert 'model_reasoning_effort="none"' in _configs(command)


def test_codex_signed_in_uses_its_own_login_and_no_endpoint_or_key():
    command = commands.codex_command(Path("codex.exe"), model="gpt-6-astra", thinking="medium",
                                     workspace=Path("W:/run"), write=False, base_url=None)
    assert "exec" in command
    assert not [setting for setting in _configs(command) if setting.startswith("model_provider")]
    env = commands.codex_env(PARENT, config_root=CONFIG, api_key=None)
    assert "CODEX_HOME" in env and "PROMETHEUS_AGENT_KEY" not in env
