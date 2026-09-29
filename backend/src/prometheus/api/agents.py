"""「检查更新」 and the Codex login (PLAN 15.4.13)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from prometheus.agents.versions import UnknownAgent

router = APIRouter()


def _agents(request: Request):
    return request.app.state.agents


def _not_ready():
    return JSONResponse({"code": "AGENTS_NOT_READY", "detail": "检查和更新 Agent 还在开发中"}, status_code=501)


@router.get("/api/agents")
def list_agents(request: Request):
    return {"agents": _agents(request).rows()}


@router.post("/api/agents/check")
def check_agents(request: Request):
    agents = _agents(request)
    return {"agents": agents.check()} if hasattr(agents, "check") else _not_ready()


@router.post("/api/agents/update-all")
def update_all_agents(request: Request):
    agents = _agents(request)
    return {"agents": agents.update_all()} if hasattr(agents, "update_all") else _not_ready()


@router.post("/api/agents/{agent_id}/install")
@router.post("/api/agents/{agent_id}/update")
def install_agent(request: Request, agent_id: str):
    agents = _agents(request)
    if not hasattr(agents, "install"):
        return _not_ready()
    try:
        return {"agents": agents.install(agent_id)}
    except UnknownAgent:
        return JSONResponse({"code": "AGENT_NOT_FOUND"}, status_code=404)


@router.get("/api/agents/codex/login")
def codex_login(request: Request):
    agents = _agents(request)
    return agents.codex_login() if hasattr(agents, "codex_login") else _not_ready()


@router.post("/api/agents/codex/login")
def start_codex_login(request: Request):
    agents = _agents(request)
    return agents.start_codex_login() if hasattr(agents, "start_codex_login") else _not_ready()
