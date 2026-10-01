"""「检查更新」 for real (PLAN 15.4.13): the latest versions from npm, and an update that installs into a
staging folder, passes the self-check and only then replaces the old copy; a failed self-check keeps
the old version. Pi included (user 2026-09-29: its self-check covers VRA's way of calling it)."""

import json
from pathlib import Path

import pytest
from prometheus.agents import versions
from prometheus.runtime import Runtime

AUTH = {"Authorization": "Bearer test-token"}
PACKAGES = {"pi": "@earendil-works/pi-coding-agent", "codex": "@openai/codex", "claude": "@anthropic-ai/claude-code"}


def _install(folder: Path, package: str, version: str) -> None:
    home = folder / "node_modules" / package
    home.mkdir(parents=True, exist_ok=True)
    (home / "package.json").write_text(json.dumps({"name": package, "version": version}), encoding="utf-8")


@pytest.fixture
def tools(tmp_path):
    """A tools folder with Pi 0.85.0 and Codex 0.151.0 installed, Claude Code not."""
    root = tmp_path / "tools"
    _install(root / "pi", PACKAGES["pi"], "0.85.0")
    (root / "pi" / "node_modules" / PACKAGES["pi"] / "dist" / "bundle").mkdir(parents=True)
    _install(root / "agents" / "codex", PACKAGES["codex"], "0.151.0")
    (root / "node").mkdir()
    return root


class FakeNpm:
    """npm view / npm install without the network: installs write a package.json."""

    def __init__(self, latest=None, fail_view=()):
        self.latest = latest or {"pi": "0.99.1", "codex": "0.159.1", "claude": "2.1.285"}
        self.fail_view = fail_view
        self.installs = []

    def view(self, package: str) -> str:
        agent = next(agent for agent, name in PACKAGES.items() if name == package)
        if agent in self.fail_view:
            raise versions.UpdateError("连不上 npm 仓库")
        return self.latest[agent]

    def install(self, folder: Path, package: str, version: str) -> None:
        self.installs.append((Path(folder), package, version))
        _install(Path(folder), package, version)


def _agents(tools, npm, checked=None, busy=lambda: False):
    runtime = Runtime(tools / "node" / "node.exe",
                      tools / "pi" / "node_modules" / PACKAGES["pi"] / "dist" / "bundle" / "cli.js", None, None)
    checks = checked if checked is not None else []

    def selfcheck(staging_root: Path, agent_id: str):
        checks.append((staging_root, agent_id))

    return versions.LocalAgents(lambda: runtime, npm=npm, selfcheck=selfcheck, busy=busy), checks


def _by_id(rows):
    return {row["id"]: row for row in rows}


def test_the_rows_show_what_is_installed(tools):
    rows = _by_id(_agents(tools, FakeNpm())[0].rows())
    assert (rows["pi"]["version"], rows["codex"]["version"], rows["claude"]["version"]) == ("0.85.0", "0.151.0", None)


def test_check_asks_npm_for_the_latest_and_says_which_it_could_not_reach(tools):
    rows = _by_id(_agents(tools, FakeNpm(fail_view=("claude",)))[0].check())
    assert (rows["pi"]["latest"], rows["codex"]["latest"]) == ("0.99.1", "0.159.1")
    assert rows["claude"]["latest"] is None and "npm" in rows["claude"]["error"]


def test_an_update_installs_into_staging_passes_the_self_check_then_replaces_the_old_copy(tools):
    npm = FakeNpm()
    agents, checks = _agents(tools, npm)
    agents.check()
    rows = _by_id(agents.install("codex"))
    assert rows["codex"]["version"] == "0.159.1" and rows["codex"]["latest"] == "0.159.1"
    staging, package, version = npm.installs[0]
    assert package == PACKAGES["codex"] and version == "0.159.1"
    assert staging != tools / "agents" / "codex" and not staging.exists()  # moved into place
    assert checks and checks[0][1] == "codex" and staging.is_relative_to(checks[0][0])
    assert json.loads((tools / "agents" / "codex" / "node_modules" / PACKAGES["codex"] / "package.json")
                      .read_text(encoding="utf-8"))["version"] == "0.159.1"


def test_a_failed_self_check_keeps_the_old_version(tools):
    npm = FakeNpm()
    runtime = Runtime(tools / "node" / "node.exe",
                      tools / "pi" / "node_modules" / PACKAGES["pi"] / "dist" / "bundle" / "cli.js", None, None)

    def broken(staging_root, agent_id):
        raise versions.UpdateError("自检：一次性调用没有回答")

    agents = versions.LocalAgents(lambda: runtime, npm=npm, selfcheck=broken, busy=lambda: False)
    agents.check()
    with pytest.raises(versions.UpdateError, match="自检"):
        agents.install("pi")
    assert _by_id(agents.rows())["pi"]["version"] == "0.85.0"
    assert not [path for path in tools.rglob("*") if ".staging" in path.parts]


def test_installing_a_missing_agent_and_update_all(tools):
    agents, _checks = _agents(tools, FakeNpm())
    rows = _by_id(agents.install("claude"))
    assert rows["claude"]["version"] == "2.1.285"
    rows = _by_id(agents.update_all())
    assert all(row["version"] == row["latest"] for row in rows.values())


def test_nothing_is_updated_while_a_task_is_running(tools):
    agents, _checks = _agents(tools, FakeNpm(), busy=lambda: True)
    with pytest.raises(versions.UpdateError, match="任务"):
        agents.install("codex")
    assert _by_id(agents.rows())["codex"]["version"] == "0.151.0"


def test_the_api_reports_a_failed_update_with_its_reason(client_factory, tmp_path, monkeypatch):
    real = client_factory(data_dir=tmp_path / "data", fake=False)

    class Failing:
        def rows(self):
            return []

        def install(self, agent_id):
            raise versions.UpdateError("自检：一次性调用没有回答，保留原来的版本")

    real.app.state.agents = Failing()
    try:
        answer = real.post("/api/agents/codex/update", headers=AUTH)
    except versions.UpdateError:
        answer = None
    assert answer is not None and answer.status_code == 409 and "保留原来的版本" in answer.json()["detail"]


def _held(monkeypatch, path: Path, times: int) -> list:
    """`path` refuses to be renamed `times` times, as a file a virus scanner still has open does on Windows."""
    original = Path.rename
    refused = []

    def rename(self, target):
        if Path(self) == path and len(refused) < times:
            refused.append(target)
            raise PermissionError(13, "拒绝访问。", str(self))
        return original(self, target)

    monkeypatch.setattr(versions.Path, "rename", rename)
    return refused


def test_a_new_copy_held_open_for_a_moment_still_goes_in(tools, monkeypatch):
    """Installed run 2026-10-01: the swap of a just-downloaded Codex got 「拒绝访问」 once in three runs."""
    waits = []
    monkeypatch.setattr(versions.time, "sleep", waits.append)
    refused = _held(monkeypatch, tools / ".staging" / "agents" / "codex", times=3)
    agents, _checks = _agents(tools, FakeNpm())
    rows = _by_id(agents.install("codex"))
    assert len(refused) == 3 and len(waits) == 3
    assert rows["codex"]["version"] == "0.159.1"


def test_a_copy_held_for_good_keeps_the_old_version_after_a_minute_of_tries(tools, monkeypatch):
    waits = []
    monkeypatch.setattr(versions.time, "sleep", waits.append)
    _held(monkeypatch, tools / ".staging" / "agents" / "codex", times=10_000)
    agents, _checks = _agents(tools, FakeNpm())
    with pytest.raises(versions.UpdateError, match="保留原来的版本"):
        agents.install("codex")
    assert 55 <= sum(waits) <= 65
    assert _by_id(agents.rows())["codex"]["version"] == "0.151.0"
