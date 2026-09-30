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
# The profile's 「上下文窗口」 is the endpoint's real limit (runanytime refused what anyrouter took,
# 2026-09-30): Codex compacts its history at 80 % of it, well before the relay says no.
COMPACT_AT = 0.8


def executable(tools_root, agent_id: str) -> Path:
    return Path(tools_root) / EXECUTABLES[agent_id]


def tools_root(pi_cli) -> Path:
    """<tools>/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js -> <tools>."""
    parents = Path(pi_cli).parents
    return parents[6] if len(parents) > 6 else Path(pi_cli).parent


def clean_env(env: dict) -> dict:
    return {name: value for name, value in env.items() if not name.upper().startswith(INHERITED)}


def claude_model(model: str, context_window) -> str:
    """Claude Code gives a Claude model 200k unless its name asks for 「[1m]」; Pi gives it what the
    catalogue says (claude-opus-4-8: 1M), so a 1M window adds the suffix."""
    if context_window and context_window >= 1_000_000 and not model.endswith("[1m]"):
        return f"{model}[1m]"
    return model


def claude_command(exe, *, model: str, thinking: str, tools, system: str = "") -> list:
    """`tools`: True for a workspace task, "Read" to look at images, False for plain text; `system`
    is appended to Claude Code's system prompt, as Pi's --append-system-prompt."""
    command = [str(exe), "-p", "--bare", "--output-format", "stream-json", "--verbose", "--model", model,
               "--effort", CLAUDE_EFFORT.get(thinking, thinking), "--no-session-persistence",
               "--strict-mcp-config", "--disable-slash-commands"]
    if system:
        command += ["--append-system-prompt", system]
    allowed = CLAUDE_TOOLS if tools is True else (tools or "")
    if allowed:
        return command + ["--tools", allowed, "--allowedTools", allowed, "--permission-mode", "dontAsk"]
    return command + ["--tools", ""]


def _anthropic_base(base_url: str) -> str:
    """Claude Code appends /v1/messages itself, as Pi does (llm/pi_models.custom_base_url)."""
    base = (base_url or "").rstrip("/")
    return base.removesuffix("/v1")


def claude_env(env: dict, *, config_root, base_url: str, api_key: str, max_tokens=None, context_window=None) -> dict:
    """The profile's 「最大输出」 and 「上下文窗口」: a 1M window also comes with the model name
    (「[1m]」); any other one Claude Code only knows from CLAUDE_CODE_MAX_CONTEXT_TOKENS."""
    limit = {"CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(max_tokens)} if max_tokens else {}
    if context_window:
        limit["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(context_window)
    return {**clean_env(env), **limit, "CLAUDE_CONFIG_DIR": str(Path(config_root) / "claude"),
            "ANTHROPIC_BASE_URL": _anthropic_base(base_url), "ANTHROPIC_API_KEY": api_key,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_MAX_RETRIES": str(RETRIES)}


def codex_command(exe, *, model: str, thinking: str, workspace, write: bool, base_url, images=(), context_window=None,
                  max_tokens=None, system: str = "") -> list:
    """`base_url` None: the app's own ChatGPT login instead of an endpoint and a key. A task that
    writes runs without Codex's own sandbox: on Windows it refuses every command when there is no
    window to ask in, and every run is contained instead (contain.py, user 2026-09-29)."""
    command = [str(exe), "exec", "--json", "--model", model, "--ephemeral", "--ignore-user-config", "--ignore-rules",
               "--skip-git-repo-check", "--sandbox", "danger-full-access" if write else "read-only", "-C", str(workspace)]
    # verbosity: Codex sends 「low」 for its GPT models; Pi sends none, so the API default (medium) applies
    settings = [f"model_reasoning_effort={json.dumps(CODEX_EFFORT.get(thinking, thinking))}", 'approval_policy="never"',
                'model_verbosity="medium"', "project_doc_max_bytes=0",
                "skills.include_instructions=false", 'web_search="disabled"', "check_for_update_on_startup=false"]
    if base_url:
        settings += ['model_provider="prometheus"', 'model_providers.prometheus.name="prometheus"',
                     f"model_providers.prometheus.base_url={json.dumps(base_url)}",
                     'model_providers.prometheus.wire_api="responses"',
                     f'model_providers.prometheus.env_key="{KEY_VARIABLE}"',
                     f"model_providers.prometheus.request_max_retries={RETRIES}",
                     f"model_providers.prometheus.stream_max_retries={RETRIES}"]
    if context_window:  # the endpoint's own limit: Codex compacts by the window it believes in
        settings += [f"model_context_window={context_window}",
                     f"model_auto_compact_token_limit={int(context_window * COMPACT_AT)}"]
    # max_tokens: Codex has no output cap to set (no such key in 0.159; the request carries none)
    if system:  # appended to the model's instructions, as Pi's --append-system-prompt
        settings.append(f"developer_instructions={json.dumps(system, ensure_ascii=False)}")
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
