"""Running a model call through Codex CLI or Claude Code (PLAN 15.4.13): a one-shot text call, or a
task in a workspace that must leave a named file behind. Pi keeps its own paths (llm/one_shot.py,
report/pi_run.py); they hand over here when the profile names another Agent."""


class AgentRunError(RuntimeError):
    code = "EXTERNAL_MODEL_FAILURE"


def agent_of(llm: dict) -> dict:
    """The Agent part of the settings' ``llm`` view: which one, how it connects, where to."""
    return {"id": llm.get("agent") or "pi", "access": llm.get("access") or "key",
            "base_url": llm.get("base_url") or (llm.get("custom") or {}).get("base_url", "")}


def one_shot(agent: dict, **kwargs) -> str:
    raise NotImplementedError


def task(agent: dict, workspace, prompt: str, **kwargs):
    raise NotImplementedError
