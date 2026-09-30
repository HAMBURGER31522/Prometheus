"""How the app starts its own Codex CLI and Claude Code (PLAN 15.4.13).

Both are the app's private copies under the tools folder's ``agents/``, each with its own config
folder under the data folder's ``.prometheus/config/``. The switches keep the user's own plugins,
hooks, instructions, skills, MCP servers and history out, and turn off what Pi does not have either
(checked 2026-09-29 with Claude Code 2.1.285 and Codex 0.159.0 against a local fake API: with the
switches nothing planted in the home or project folders reached the model; without them all of it
did). The endpoint and the key travel only in the child's environment, never on its command line.
"""

import json
from pathlib import Path

EXECUTABLES = {
    "claude": Path("agents/claude/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
    "codex": Path("agents/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"),
}
# What another agent (or the terminal the app was started from) leaves in the environment.
INHERITED = ("ANTHROPIC_", "CLAUDE", "CODEX_", "OPENAI_")
# Pi's read / write / edit / powershell: in --bare Claude Code writes files through Edit.
CLAUDE_TOOLS = "Read,Edit,PowerShell"
CLAUDE_EFFORT = {"off": "low"}  # --effort starts at low
CODEX_EFFORT = {"off": "none"}
# On by default in Codex, missing in Pi: a plugin marketplace it downloads, web search, sub-agents…
CODEX_OFF = ("plugins", "remote_plugin", "plugin_sharing", "apps", "browser_use", "browser_use_external",
             "computer_use", "goals", "hooks", "image_generation", "multi_agent", "skill_search", "tool_suggest",
             "sleep_tool", "in_app_updates", "realtime_conversation",
             "unbounded_connection_retries")  # else an unreachable endpoint is tried forever
KEY_VARIABLE = "PROMETHEUS_AGENT_KEY"
# Pi tries a failed request three times itself; the stage's relay retry comes on top (report/workspace.py).
RETRIES = 3


def executable(tools_root, agent_id: str) -> Path:
    return Path(tools_root) / EXECUTABLES[agent_id]


def tools_root(pi_cli) -> Path:
    """<tools>/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js -> <tools>."""
    parents = Path(pi_cli).parents
    return parents[6] if len(parents) > 6 else Path(pi_cli).parent


def clean_env(env: dict) -> dict:
    return {name: value for name, value in env.items() if not name.upper().startswith(INHERITED)}


def claude_command(exe, *, model: str, thinking: str, tools) -> list:
    """`tools`: True for a workspace task, "Read" to look at images, False for plain text."""
    command = [str(exe), "-p", "--bare", "--output-format", "stream-json", "--verbose", "--model", model,
               "--effort", CLAUDE_EFFORT.get(thinking, thinking), "--no-session-persistence",
               "--strict-mcp-config", "--disable-slash-commands"]
    allowed = CLAUDE_TOOLS if tools is True else (tools or "")
    if allowed:
        return command + ["--tools", allowed, "--allowedTools", allowed, "--permission-mode", "dontAsk"]
    return command + ["--tools", ""]


def _anthropic_base(base_url: str) -> str:
    """Claude Code appends /v1/messages itself, as Pi does (llm/pi_models.custom_base_url)."""
    base = (base_url or "").rstrip("/")
    return base.removesuffix("/v1")


def claude_env(env: dict, *, config_root, base_url: str, api_key: str) -> dict:
    return {**clean_env(env), "CLAUDE_CONFIG_DIR": str(Path(config_root) / "claude"),
            "ANTHROPIC_BASE_URL": _anthropic_base(base_url), "ANTHROPIC_API_KEY": api_key,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_MAX_RETRIES": str(RETRIES)}


def codex_command(exe, *, model: str, thinking: str, workspace, write: bool, base_url, images=()) -> list:
    """`base_url` None: the app's own ChatGPT login instead of an endpoint and a key. A task that
    writes runs without Codex's own sandbox: on Windows it refuses every command when there is no
    window to ask in, and every run is contained instead (contain.py, user 2026-09-29)."""
    command = [str(exe), "exec", "--json", "--model", model, "--ephemeral", "--ignore-user-config", "--ignore-rules",
               "--skip-git-repo-check", "--sandbox", "danger-full-access" if write else "read-only", "-C", str(workspace)]
    settings = [f"model_reasoning_effort={json.dumps(CODEX_EFFORT.get(thinking, thinking))}", 'approval_policy="never"',
                "project_doc_max_bytes=0",
                "skills.include_instructions=false", 'web_search="disabled"', "check_for_update_on_startup=false"]
    if base_url:
        settings += ['model_provider="prometheus"', 'model_providers.prometheus.name="prometheus"',
                     f"model_providers.prometheus.base_url={json.dumps(base_url)}",
                     'model_providers.prometheus.wire_api="responses"',
                     f'model_providers.prometheus.env_key="{KEY_VARIABLE}"',
                     f"model_providers.prometheus.request_max_retries={RETRIES}",
                     f"model_providers.prometheus.stream_max_retries={RETRIES}"]
    for setting in settings:
        command += ["-c", setting]
    for feature in CODEX_OFF:
        command += ["--disable", feature]
    if images:
        command += ["--image", *(str(image) for image in images)]
    # the prompt comes on stdin; without 「--」 --image would take 「-」 for one more picture
    return command + ["--", "-"]


def codex_env(env: dict, *, config_root, api_key) -> dict:
    ready = {**clean_env(env), "CODEX_HOME": str(Path(config_root) / "codex")}
    return {**ready, KEY_VARIABLE: api_key} if api_key else ready
