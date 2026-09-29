"""The self-check after an update (PLAN 15.4.13): run the new copy against the local fake model API —
a one-shot call and a workspace task for every Agent, and for Pi also VRA's own run (its PiRunner,
written for a fixed Pi event format; user 2026-09-29) — before it replaces the old one. A copy that
cannot do them fails. Real programs, no network; run with -m agents."""

import os
import shutil
from pathlib import Path

import pytest
from prometheus.agents import selfcheck, versions

pytestmark = pytest.mark.agents
TOOLS = Path(os.environ.get("PROMETHEUS_TOOLS") or "E:/tools/Prometheus-Desktop")
NODE = TOOLS / "node" / "node.exe"


@pytest.mark.parametrize("agent_id", ["pi", "claude", "codex"])
def test_the_installed_copies_pass(agent_id, tmp_path):
    selfcheck.run(TOOLS, agent_id, node_exe=NODE, scratch=tmp_path)


def test_a_broken_copy_fails(tmp_path):
    staging = tmp_path / "staging"
    exe = staging / "agents" / "claude" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"not a program")
    with pytest.raises(versions.UpdateError, match="自检"):
        selfcheck.run(staging, "claude", node_exe=NODE, scratch=tmp_path / "scratch")


def test_a_pi_that_breaks_vras_run_fails(tmp_path):
    """A Pi whose runs never settle the way VRA waits for: copy the real one, then break its cli."""
    staging = tmp_path / "staging"
    shutil.copytree(TOOLS / "pi", staging / "pi")
    cli = staging / "pi" / "node_modules" / "@earendil-works" / "pi-coding-agent" / "dist" / "bundle" / "cli.js"
    cli.write_text("process.exit(0);", encoding="utf-8")
    with pytest.raises(versions.UpdateError, match="自检"):
        selfcheck.run(staging, "pi", node_exe=NODE, scratch=tmp_path / "scratch")
