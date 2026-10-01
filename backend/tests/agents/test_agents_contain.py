"""File protection for every Agent run (PLAN 15.4.13, user 2026-09-29): Pi, Codex CLI and Claude Code,
and everything they start, run at Windows' low integrity level; only the run's own folders are
labelled writable, so nothing else on the machine can be changed or deleted, whatever the model asks.
No administrator rights are needed."""

import subprocess
import sys
import time
from pathlib import Path

import pytest
from prometheus.agents import commands, contain, runs
from prometheus.llm import capability, one_shot
from prometheus.report import pi_run
from prometheus.report import workspace as workspace_mod

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
LAUNCHER = [sys.executable, "-m", "prometheus.agents.contain"]


def _folders(tmp_path):
    inside, outside, temp = tmp_path / "run", tmp_path / "elsewhere", tmp_path / "agent" / "tmp"
    inside.mkdir()
    outside.mkdir()
    canary = outside / "canary.txt"
    canary.write_text("do not delete", encoding="utf-8")
    return inside, outside, temp, canary


def _contained(tmp_path, script: str, **kwargs):
    inside, _outside, temp, _canary = _folders(tmp_path)
    return subprocess.run([*contain.prefix([inside], temp=temp), POWERSHELL, "-NoProfile", "-Command", script],
                          capture_output=True, cwd=inside, check=False, **kwargs)


def test_the_prefix_names_the_writable_folders_and_the_temp_folder(tmp_path):
    prefix = contain.prefix([tmp_path / "a", tmp_path / "b"], temp=tmp_path / "t")
    assert prefix[:3] == LAUNCHER and prefix[-1] == "--"
    assert prefix[3:-1] == ["--writable", str(tmp_path / "a"), "--writable", str(tmp_path / "b"), "--temp", str(tmp_path / "t")]


def test_a_contained_program_writes_in_its_folder_but_cannot_delete_or_write_anything_else(tmp_path):
    inside, outside, temp, canary = _folders(tmp_path)
    script = (f"Set-Content -LiteralPath '{inside / 'ch-01.html'}' -Value ok; "
              f"Remove-Item -LiteralPath '{canary}' -ErrorAction SilentlyContinue; "
              f"Set-Content -LiteralPath '{outside / 'written.txt'}' -Value bad -ErrorAction SilentlyContinue; "
              f"Set-Content -LiteralPath (Join-Path $env:TEMP 'scratch.txt') -Value ok; exit 7")
    result = subprocess.run([*contain.prefix([inside], temp=temp), POWERSHELL, "-NoProfile", "-Command", script],
                            capture_output=True, cwd=inside, timeout=120, check=False)
    assert result.returncode == 7
    assert (inside / "ch-01.html").is_file() and (temp / "scratch.txt").is_file()
    assert canary.read_text(encoding="utf-8") == "do not delete"
    assert not (outside / "written.txt").exists()


def test_stdin_and_stdout_pass_through(tmp_path):
    result = _contained(tmp_path, "$text = [Console]::In.ReadToEnd(); Write-Output ('got ' + $text.Trim())",
                        input="你好".encode(), timeout=120)
    assert result.returncode == 0 and "got 你好" in result.stdout.decode("utf-8", "replace")


def test_the_program_ends_when_its_launcher_is_stopped(tmp_path):
    inside, _outside, temp, _canary = _folders(tmp_path)
    marker = inside / "pid.txt"
    script = f"Set-Content -LiteralPath '{marker}' -Value $PID; Start-Sleep -Seconds 60"
    launcher = subprocess.Popen([*contain.prefix([inside], temp=temp), POWERSHELL, "-NoProfile", "-Command", script],
                                cwd=inside, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if marker.is_file() and marker.read_text(encoding="utf-8", errors="replace").strip():
            break
        time.sleep(0.2)
    pid = int(marker.read_text(encoding="utf-8-sig").strip())
    launcher.kill()
    launcher.wait()
    time.sleep(1.5)
    # tasklist answers in the console's code page (GBK here): read as UTF-8 its 「没有运行的任务」 was None
    alive = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, check=False).stdout
    alive = alive.decode("utf-8", errors="replace")
    assert str(pid) not in alive


# ---- every start of an Agent goes through it ----

def _writable(command):
    return [command[i + 1] for i, part in enumerate(command) if part == "--writable"]


def test_pi_one_shots_run_contained_with_pis_own_folder_writable(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(one_shot.subprocess, "run",
                        lambda command, **kwargs: seen.append(command) or subprocess.CompletedProcess(command, 0, b"", b""))
    one_shot.run_one_shot(tmp_path, prompt="你好", provider="deepseek", model="m", api_key="k", thinking="low",
                          node_exe="node.exe", pi_cli="cli.js", agent_dir=tmp_path / "config" / "pi")
    assert seen and seen[0][:3] == LAUNCHER and _writable(seen[0]) == [str(tmp_path / "config" / "pi")]
    assert seen[0][seen[0].index("--") + 1:][:2] == ["node.exe", "cli.js"]


def test_pi_workspace_runs_run_contained_with_the_workspace_writable(monkeypatch, tmp_path):
    seen = []

    async def fake_run(command, workspace, prompt, env, timeout):
        seen.append(command)
        (workspace / "plan.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(pi_run, "_run", fake_run)
    pi_run.run_task(tmp_path / "run", "写", expect="plan.json", llm={"provider": "deepseek", "model": "m"},
                    prefix=["node.exe", "cli.js"], agent_dir=tmp_path / "config" / "pi", timeout=60)
    assert seen and seen[0][:3] == LAUNCHER
    assert _writable(seen[0]) == [str(tmp_path / "run"), str(tmp_path / "config" / "pi")]


def test_pis_model_listing_runs_contained(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(capability.subprocess, "run",
                        lambda command, **kwargs: seen.append(command) or subprocess.CompletedProcess(command, 0, b"", b""))
    capability.pi_model_listing("node.exe", "cli.js", tmp_path, {"provider": "deepseek"})
    assert seen and seen[0][:3] == LAUNCHER


def test_the_standard_report_runs_pi_contained_in_its_work_folder(monkeypatch, tmp_path):
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store
    from prometheus.settings import store

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    seen = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def run(self, work):
            return work / "report.html"

    monkeypatch.setattr(workspace_mod, "PiRunner", FakeRunner)
    workspace_mod.run_report_stage(data_dir, item_id, items_store.get_item(data_dir, item_id), store.load(data_dir),
                                   node_exe="node.exe", pi_cli="cli.js")
    prefix = seen["command_prefix"]
    assert prefix[:3] == LAUNCHER and prefix[-2:] == ["node.exe", "cli.js"]
    assert str(paths.work_dir(data_dir, item_id)) in _writable(prefix)


@pytest.mark.parametrize("agent_id", ["claude", "codex"])
def test_codex_and_claude_code_tasks_run_contained_with_their_own_folders_writable(monkeypatch, tmp_path, agent_id):
    seen = []

    def fake_run(command, **kwargs):
        seen.append(command)
        (Path(kwargs["cwd"]) / "ch-01.html").write_text("ok", encoding="utf-8")
        stream = (Path(__file__).parents[1] / "fixtures" / "agents" / f"{agent_id}-answer.jsonl").read_bytes()
        return subprocess.CompletedProcess(command, 0, stream, b"")

    monkeypatch.setattr(runs.subprocess, "run", fake_run)
    agent = {"id": agent_id, "access": "key", "base_url": "https://relay.example"}
    (tmp_path / "run").mkdir()
    runs.task(agent, tmp_path / "run", "写", expect="ch-01.html", model="m", api_key="k", thinking="medium",
              config_root=tmp_path / "config", tools_root=tmp_path / "tools", timeout=60)
    assert seen and seen[0][:3] == LAUNCHER
    assert _writable(seen[0]) == [str(tmp_path / "run"), str(tmp_path / "config" / agent_id)]
    assert seen[0][seen[0].index("--") + 1] == str(commands.executable(tmp_path / "tools", agent_id))


def test_codex_tasks_leave_its_windows_sandbox_off_and_never_ask():
    """Its sandbox refuses every command when run without a window on Windows; the protection above
    takes its place."""
    command = commands.codex_command(Path("codex.exe"), model="m", thinking="medium", workspace=Path("W:/run"),
                                     write=True, base_url="https://relay.example/v1")
    assert command[command.index("--sandbox") + 1] == "danger-full-access"
    configs = [command[i + 1] for i, part in enumerate(command) if part == "-c"]
    assert 'approval_policy="never"' in configs
