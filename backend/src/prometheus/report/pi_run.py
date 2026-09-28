"""Our own Pi runs for 完整精读 (PLAN 15.4.11). Stub."""

from pathlib import Path

SKILL_DIR = Path(".")


class PiRunError(RuntimeError):
    code = "EXTERNAL_MODEL_FAILURE"


def pi_command(prefix: list, workspace, llm: dict, *, tools: str = "read,write,edit,powershell") -> list:
    return list(prefix)


def run_task(workspace, prompt: str, *, expect: str, llm: dict, prefix: list, agent_dir, timeout: float) -> Path:
    return Path(workspace) / expect


def stage_skill(workspace) -> None:
    return None
