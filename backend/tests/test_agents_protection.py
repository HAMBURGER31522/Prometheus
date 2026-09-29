"""E15 Done When 2, file protection (PLAN 15.4.13, user 2026-09-29): a model that tells Pi, Codex CLI
or Claude Code to delete a file outside the run's folder, or to write one there, gets nowhere, while
the chapter it writes inside comes out as usual. The same run without the protection does lose the
bait file: the check can fail. Real CLIs against the local fake model API; run with -m agents."""

import json
import os
from pathlib import Path

import pytest
from prometheus.agents import contain, fake_api, runs
from prometheus.report import pi_run

pytestmark = pytest.mark.agents
TOOLS = Path(os.environ.get("PROMETHEUS_TOOLS") or "E:/tools/Prometheus-Desktop")
PI = [str(TOOLS / "node" / "node.exe"),
      str(TOOLS / "pi" / "node_modules" / "@earendil-works" / "pi-coding-agent" / "dist" / "bundle" / "cli.js")]


def _run(agent_id: str, api, root: Path, prompt: str) -> Path:
    config = root / "data" / ".prometheus" / "config"
    workspace = root / "data" / "run"
    workspace.mkdir(parents=True, exist_ok=True)
    if agent_id == "pi":
        (config / "pi").mkdir(parents=True, exist_ok=True)
        (config / "pi" / "models.json").write_text(json.dumps({"providers": {"custom": {
            "baseUrl": api.url, "api": "anthropic-messages", "apiKey": "sk-fake",
            "models": [{"id": "fake-model", "name": "fake-model", "reasoning": False, "input": ["text"],
                        "contextWindow": 200000, "maxTokens": 8192}]}}}), encoding="utf-8")
        return pi_run.run_task(workspace, prompt, expect="ch-01.html", timeout=300, agent_dir=config / "pi", prefix=PI,
                               llm={"provider": "custom", "model": "fake-model", "api_key": "sk-fake"})
    agent = {"id": agent_id, "access": "key", "base_url": api.url if agent_id == "claude" else f"{api.url}/v1"}
    return runs.task(agent, workspace, prompt, expect="ch-01.html", model="fake-model", api_key="sk-fake",
                     thinking="medium", config_root=config, tools_root=TOOLS, timeout=300)


def _bait(root: Path):
    elsewhere = root / "elsewhere"
    elsewhere.mkdir()
    canary = elsewhere / "canary.txt"
    canary.write_text("do not delete", encoding="utf-8")
    target = root / "data" / "run" / "ch-01.html"
    return canary, elsewhere / "written.txt", target, f"DELETE:{canary}\nOUTSIDE:{elsewhere / 'written.txt'}\nWRITE:{target}"


@pytest.mark.parametrize("agent_id", ["pi", "claude", "codex"])
def test_a_contained_agent_cannot_delete_or_write_outside_its_folder(tmp_path, agent_id):
    canary, outside, target, prompt = _bait(tmp_path)
    with fake_api.FakeModelApi() as api:
        written = _run(agent_id, api, tmp_path, prompt)
        assert len(api.requests) >= 3  # it did try: the delete, then the chapter, then the answer
    assert written == target and target.read_text(encoding="utf-8").strip() == "ok"
    assert canary.read_text(encoding="utf-8") == "do not delete"
    assert not outside.exists()


@pytest.mark.parametrize("agent_id", ["pi", "claude", "codex"])
def test_without_the_protection_the_bait_is_gone(tmp_path, monkeypatch, agent_id):
    monkeypatch.setattr(contain, "prefix", lambda writable, *, temp: [])
    canary, outside, _target, prompt = _bait(tmp_path)
    with fake_api.FakeModelApi() as api:
        _run(agent_id, api, tmp_path, prompt)
    assert not canary.exists() and outside.exists()
