"""What each Agent takes (PLAN 15.4.13): Pi runs every protocol and the built-in providers; Codex CLI
speaks the OpenAI protocol and can sign in with a ChatGPT account; Claude Code speaks Anthropic's."""

AGENTS = (
    {"id": "pi", "name": "Pi", "package": "@earendil-works/pi-coding-agent"},
    {"id": "codex", "name": "Codex CLI", "package": "@openai/codex"},
    {"id": "claude", "name": "Claude Code", "package": "@anthropic-ai/claude-code"},
)
IDS = tuple(agent["id"] for agent in AGENTS)
ACCESS = ("key", "login")
PROTOCOL = {"codex": "openai", "claude": "anthropic"}
LOGIN = ("codex",)


def problem(profile: dict) -> str | None:
    """Why a profile cannot be saved, as the API's error code; None when it can."""
    agent, access = profile.get("agent", "pi"), profile.get("access", "key")
    if agent not in IDS:
        return "INVALID_AGENT"
    if access not in ACCESS or (access == "login" and agent not in LOGIN):
        return "INVALID_ACCESS"
    if agent == "pi" or access == "login":
        return None
    if profile.get("kind", "custom") != "custom":  # DeepSeek and 智谱 as kinds are Pi's own providers
        return "AGENT_NEEDS_ENDPOINT"
    if profile.get("protocol", "openai") != PROTOCOL[agent]:
        return "AGENT_PROTOCOL_MISMATCH"
    return None
