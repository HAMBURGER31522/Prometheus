from pathlib import Path


def executable(tools_root, agent_id: str) -> Path:
    return Path()


def clean_env(env: dict) -> dict:
    return dict(env)


def claude_command(exe, *, model: str, thinking: str, tools: bool) -> list:
    return []


def claude_env(env: dict, *, config_root, base_url: str, api_key: str) -> dict:
    return {}


def codex_command(exe, *, model: str, thinking: str, workspace, write: bool, base_url) -> list:
    return []


def codex_env(env: dict, *, config_root, api_key) -> dict:
    return {}
