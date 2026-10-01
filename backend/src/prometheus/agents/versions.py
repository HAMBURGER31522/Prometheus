"""The Agents' versions for 「检查更新」 and the Codex login (PLAN 15.4.13).

Codex CLI and Claude Code are the app's own copies under the tools folder's ``agents/<id>/``, apart
from any the user installed. The fake backend simulates checking, installing, updating and signing
in, so the settings page can be built and seen before the real ones exist.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from prometheus.agents import commands
from prometheus.agents.rules import AGENTS
from prometheus.runtime import RuntimeConfigError

PACKAGES = {agent["id"]: agent["package"] for agent in AGENTS}
# Where each copy lives under the tools folder; updates are staged in <tools>/.staging first.
FOLDERS = {"pi": Path("pi"), "codex": Path("agents/codex"), "claude": Path("agents/claude")}
# A just-downloaded copy can be held open for a while (virus scan, indexer) and Windows then refuses the
# rename; npm retries the same way. Every half second for a minute, then the old version stays (PLAN 15.4.17-9).
SWAP_WAIT_S = 0.5
SWAP_TRIES = 120


def _rename(source: Path, target: Path) -> None:
    for attempt in range(SWAP_TRIES + 1):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == SWAP_TRIES:
                raise
            time.sleep(SWAP_WAIT_S)


class UnknownAgent(KeyError):
    pass


class UpdateError(RuntimeError):
    pass


def _row(agent: dict, version, latest, error=None) -> dict:
    return {"id": agent["id"], "name": agent["name"], "installed": version is not None, "version": version,
            "latest": latest, "error": error}


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

    def codex_models(self) -> list:
        return [{"id": "gpt-6-astra", "levels": ["low", "medium", "high", "xhigh", "max"], "images": True},
                {"id": "gpt-5.5", "levels": ["low", "medium"], "images": True}]


def _version(package_json: Path):
    try:
        return json.loads(package_json.read_text(encoding="utf-8")).get("version") or "?"
    except (OSError, ValueError):
        return None


class NpmRegistry:
    """npm through the bundled node: the latest version of a package, and installing one into a folder."""

    def __init__(self, node_exe, *, cache=None, proxy: str = ""):
        self.node = Path(node_exe)
        self.cli = self.node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        self.env = {**os.environ, **({"npm_config_cache": str(cache)} if cache else {}),
                    **({"npm_config_proxy": proxy, "npm_config_https_proxy": proxy} if proxy.strip() else {})}

    def _npm(self, arguments: list, timeout: float) -> str:
        if not self.cli.is_file():
            raise UpdateError(f"缺少 npm（{self.cli}），无法检查和安装 Agent")
        try:
            done = subprocess.run([str(self.node), str(self.cli), *arguments], capture_output=True, env=self.env,
                                  timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpdateError(f"npm 没有完成：{exc}") from exc
        if done.returncode != 0:
            raise UpdateError("npm 出错：" + done.stderr.decode("utf-8", "replace").strip()[-300:])
        return done.stdout.decode("utf-8", "replace")

    def view(self, package: str) -> str:
        try:
            return json.loads(self._npm(["view", package, "version", "--json"], 60))
        except ValueError as exc:
            raise UpdateError(f"npm 仓库没有给出 {package} 的版本") from exc

    def install(self, folder, package: str, version: str) -> None:
        self._npm(["install", "--prefix", str(folder), f"{package}@{version}", "--no-audit", "--no-fund",
                   "--loglevel", "error"], 1800)


class LocalAgents:
    """The copies under the tools folder: their versions, the latest from npm, and updating them —
    staged, self-checked (agents/selfcheck.py), then swapped in; a failure keeps the old copy."""

    def __init__(self, get_runtime, *, npm=None, selfcheck=None, busy=None, proxy=lambda: "", config_root=None):
        self.get_runtime = get_runtime
        self._config_root = config_root or (lambda: None)
        self._codex_models = (0.0, [])
        self._npm = npm
        self._selfcheck = selfcheck
        self._busy = busy or (lambda: False)
        self._proxy = proxy
        self.latest: dict = {}
        self.errors: dict = {}

    def _tools(self) -> Path:
        pi_cli = self._pi_cli()
        if pi_cli is None:
            raise UpdateError("找不到应用的工具目录")
        return commands.tools_root(pi_cli)

    def _registry(self):
        if self._npm is None:
            node = self.get_runtime().node
            cache = self._tools() / "npm-cache"
            self._npm = NpmRegistry(node, cache=cache if cache.is_dir() else None, proxy=self._proxy())
        return self._npm

    def _check_copy(self, staging_root: Path, agent_id: str) -> None:
        if self._selfcheck is not None:
            return self._selfcheck(staging_root, agent_id)
        from prometheus.agents import selfcheck

        with tempfile.TemporaryDirectory(prefix="prometheus-selfcheck-") as scratch:
            selfcheck.run(staging_root, agent_id, node_exe=self.get_runtime().node, scratch=scratch)

    def check(self) -> list:
        for agent in AGENTS:
            try:
                self.latest[agent["id"]] = self._registry().view(agent["package"])
                self.errors.pop(agent["id"], None)
            except UpdateError as exc:
                self.latest[agent["id"]] = None
                self.errors[agent["id"]] = str(exc)
        return self.rows()

    def install(self, agent_id: str) -> list:
        """Install or update one Agent to the latest version."""
        _find(agent_id)
        if self._busy():
            raise UpdateError("有任务在运行，等它结束再更新")
        version = self.latest.get(agent_id) or self._registry().view(PACKAGES[agent_id])
        tools = self._tools()
        staging_root = tools / ".staging"
        shutil.rmtree(staging_root, ignore_errors=True)
        target = tools / FOLDERS[agent_id]
        old = target.with_name(target.name + ".old")
        try:
            staged = staging_root / FOLDERS[agent_id]
            self._registry().install(staged, PACKAGES[agent_id], version)
            self._check_copy(staging_root, agent_id)
            shutil.rmtree(old, ignore_errors=True)
            if target.exists():
                _rename(target, old)
            target.parent.mkdir(parents=True, exist_ok=True)
            _rename(staged, target)
        except OSError as exc:
            if old.exists() and not target.exists():
                old.rename(target)
            raise UpdateError(f"换上新版本时出错，保留原来的版本：{exc}") from exc
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
        self.latest[agent_id] = version
        return self.rows()

    # ---- Codex CLI's own models and login (codex_app.py) ----

    def codex_models(self) -> list:
        """Codex's model list, kept five minutes: typing a model name must not start Codex each time."""
        from prometheus.agents import codex_app

        at, found = self._codex_models
        if time.monotonic() - at > 300 or not found:
            found = codex_app.models(self._tools(), self._config_root())
            self._codex_models = (time.monotonic(), found)
        return found

    def codex_login(self) -> dict:
        from prometheus.agents import codex_app

        return {"logged_in": codex_app.logged_in(self._tools(), self._config_root())}

    def start_codex_login(self) -> dict:
        from prometheus.agents import codex_app

        codex_app.start_login(self._tools(), self._config_root())
        self._codex_models = (0.0, [])  # the account's own list once signed in
        return self.codex_login()

    def update_all(self) -> list:
        """「全部更新」: check every Agent, then bring each one that is behind to the latest."""
        self.check()
        for row in self.rows():
            if row["latest"] and row["version"] != row["latest"]:
                self.install(row["id"])
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
        return [_row(agent, found[agent["id"]], self.latest.get(agent["id"]), self.errors.get(agent["id"]))
                for agent in AGENTS]
