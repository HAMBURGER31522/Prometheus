"""The Agents' versions for 「检查更新」 and the Codex login (PLAN 15.4.13).

Codex CLI and Claude Code are the app's own copies under the tools folder's ``agents/<id>/``, apart
from any the user installed. The fake backend simulates checking, installing, updating and signing
in, so the settings page can be built and seen before the real ones exist.
"""

import json
from pathlib import Path

from prometheus.agents.rules import AGENTS
from prometheus.runtime import RuntimeConfigError


class UnknownAgent(KeyError):
    pass


class UpdateError(RuntimeError):
    pass


def _row(agent: dict, version, latest) -> dict:
    return {"id": agent["id"], "name": agent["name"], "installed": version is not None, "version": version,
            "latest": latest}


def _find(agent_id: str) -> dict:
    for agent in AGENTS:
        if agent["id"] == agent_id:
            return agent
    raise UnknownAgent(agent_id)


FAKE_LATEST = {"pi": "0.86.0", "codex": "0.153.0", "claude": "2.1.290"}


class FakeAgents:
    """Pi and an older Codex CLI installed, Claude Code not; nothing goes online."""

    def __init__(self):
        self.versions = {"pi": "0.85.0", "codex": "0.151.0", "claude": None}
        self.latest = dict.fromkeys(self.versions)
        self.codex_logged_in = False

    def rows(self) -> list:
        return [_row(agent, self.versions[agent["id"]], self.latest[agent["id"]]) for agent in AGENTS]

    def check(self) -> list:
        self.latest = dict(FAKE_LATEST)
        return self.rows()

    def install(self, agent_id: str) -> list:
        _find(agent_id)
        self.latest[agent_id] = FAKE_LATEST[agent_id]
        self.versions[agent_id] = FAKE_LATEST[agent_id]
        return self.rows()

    def update_all(self) -> list:
        for agent in AGENTS:
            self.install(agent["id"])
        return self.rows()

    def codex_login(self) -> dict:
        return {"logged_in": self.codex_logged_in}

    def start_codex_login(self) -> dict:
        self.codex_logged_in = True
        return self.codex_login()


def _version(package_json: Path):
    try:
        return json.loads(package_json.read_text(encoding="utf-8")).get("version") or "?"
    except (OSError, ValueError):
        return None


class LocalAgents:
    """What is installed on this machine; checking and updating arrive with the adapters (15.4.13 step 2)."""

    def __init__(self, get_runtime, *, npm=None, selfcheck=None, busy=None):
        self.get_runtime = get_runtime

    def check(self) -> list:
        return self.rows()

    def install(self, agent_id: str) -> list:
        return self.rows()

    def update_all(self) -> list:
        return self.rows()

    def _pi_cli(self):
        try:
            return self.get_runtime().pi_cli
        except RuntimeConfigError:
            return None

    def rows(self) -> list:
        pi_cli = self._pi_cli()
        found = {"pi": None, "codex": None, "claude": None}
        if pi_cli is not None:
            parents = Path(pi_cli).parents
            # <tools>/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js
            found["pi"] = (_version(parents[2] / "package.json") if len(parents) > 2 else None) or "?"
            if len(parents) > 6:
                tools = Path(pi_cli).parents[6]  # <tools>/pi/node_modules/@earendil-works/pi-coding-agent/...
                for agent in AGENTS[1:]:
                    found[agent["id"]] = _version(tools / "agents" / agent["id"] / "node_modules" / agent["package"]
                                                  / "package.json")
        return [_row(agent, found[agent["id"]], None) for agent in AGENTS]
