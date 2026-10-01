"""Every model call follows the profile's Agent (PLAN 15.4.13): one-shot calls (key points, the frame
ledger, the review, subtitles, the mind map, classification, 测试当前模型) and workspace runs (the
plan, the chapters, the patch). Pi stays as it was."""

import subprocess
import time

import pytest
from conftest import DUMMY_RUNTIME
from prometheus import paths
from prometheus.agents import runs
from prometheus.library import db
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.report import pi_run
from prometheus.report import workspace as workspace_mod
from prometheus.settings import store
from prometheus.subtitle import fix
from prometheus.tasks import stages as stages_mod
from prometheus.tasks.runner import StageContext

CLAUDE = {"id": "p1", "name": "中转", "kind": "custom", "base_url": "https://relay.example", "protocol": "anthropic",
          "api_key": "sk-test-0000", "model": "gpt-6-astra-cc-format[1m]", "supports_images": False,
          "thinking": "high", "context_window": None, "max_tokens": None, "agent": "claude", "access": "key"}


@pytest.fixture
def data_dir(tmp_path):
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    settings = store.load(data_dir)
    settings["llm_profiles"] = {"active": "p1", "items": [CLAUDE]}
    store.save(data_dir, settings)
    return data_dir


@pytest.fixture
def agent_calls(monkeypatch):
    """What reached the Agent adapters, and what reached Pi instead."""
    seen = {"one_shot": [], "task": [], "pi": []}

    def fake_one_shot(agent, **kwargs):
        seen["one_shot"].append({"agent": agent, **kwargs})
        return "可用"

    def fake_task(agent, workspace, prompt, **kwargs):
        seen["task"].append({"agent": agent, "workspace": workspace, "prompt": prompt, **kwargs})
        (workspace / kwargs["expect"]).write_text("done", encoding="utf-8")
        return workspace / kwargs["expect"]

    def fake_pi(command, **kwargs):
        seen["pi"].append(command)
        return subprocess.CompletedProcess(command, 0, b"pi", b"")

    monkeypatch.setattr(runs, "one_shot", fake_one_shot)
    monkeypatch.setattr(runs, "task", fake_task)
    monkeypatch.setattr(one_shot.subprocess, "run", fake_pi)
    return seen


def test_the_active_profile_names_its_agent_to_every_stage(data_dir):
    llm = store.load(data_dir)["llm"]
    assert (llm.get("agent"), llm.get("access")) == ("claude", "key")


def test_a_one_shot_call_goes_to_the_agent_with_the_model_and_its_own_config_folder(agent_calls, tmp_path):
    reply = one_shot.run_one_shot(
        tmp_path, prompt="你好", provider="custom", model="m", api_key="sk-x", thinking="high",
        node_exe="node.exe", pi_cli=str(tmp_path / "tools/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"),
        agent_dir=tmp_path / "data/.prometheus/config/pi", files=[tmp_path / "f.jpg"],
        agent={"id": "claude", "access": "key", "base_url": "https://relay.example"},
    )
    assert reply == "可用" and agent_calls["pi"] == [] and len(agent_calls["one_shot"]) == 1
    call = agent_calls["one_shot"][0]
    assert call["agent"]["id"] == "claude" and (call["prompt"], call["model"], call["api_key"]) == ("你好", "m", "sk-x")
    assert call["config_root"] == tmp_path / "data/.prometheus/config" and call["tools_root"] == tmp_path / "tools"
    assert call["files"] == [tmp_path / "f.jpg"] and call["work_dir"] == tmp_path


def test_without_an_agent_or_with_pi_the_call_stays_on_pi(agent_calls, tmp_path):
    for agent in (None, {"id": "pi", "access": "key", "base_url": ""}):
        one_shot.run_one_shot(tmp_path, prompt="你好", provider="deepseek", model="m", api_key="k", thinking="low",
                              node_exe="node.exe", pi_cli="cli.js", agent_dir=tmp_path, agent=agent)
    assert len(agent_calls["pi"]) == 2 and agent_calls["one_shot"] == []


def test_a_workspace_run_goes_to_the_agent(agent_calls, monkeypatch, tmp_path):
    monkeypatch.setattr(pi_run, "_run", lambda *args: pytest.fail("Pi ran"))
    llm = {"provider": "custom", "model": "m", "thinking": "high", "api_key": "sk-x", "agent": "claude",
           "access": "key", "base_url": "https://relay.example"}
    written = pi_run.run_task(tmp_path, "写 plan.json", expect="plan.json", llm=llm, prefix=["node.exe", "cli.js"],
                              agent_dir=tmp_path / "config/pi", timeout=60)
    assert written == tmp_path / "plan.json" and len(agent_calls["task"]) == 1
    call = agent_calls["task"][0]
    assert call["agent"]["id"] == "claude" and call["prompt"] == "写 plan.json" and call["timeout"] == 60


def test_the_report_stages_pass_the_agent_to_their_calls(data_dir, agent_calls, monkeypatch, tmp_path):
    async def pi_writes(command, workspace, prompt, env, timeout):
        agent_calls["pi"].append(command)
        (workspace / "ch-01.html").write_text("pi", encoding="utf-8")

    monkeypatch.setattr(pi_run, "_run", pi_writes)
    settings = store.load(data_dir)
    workspace_mod.model_ask(data_dir, tmp_path, settings, "node.exe", "cli.js")("要点")
    workspace_mod.model_look(data_dir, tmp_path, settings, "node.exe", "cli.js")("看图", [tmp_path / "f.jpg"])
    run = workspace_mod.pi_runner(data_dir, settings, "node.exe", "cli.js", deadline=time.monotonic() + 100)
    run(tmp_path, "写一章", "ch-01.html")
    assert [call["agent"]["id"] for call in agent_calls["one_shot"]] == ["claude", "claude"]
    assert [call["agent"]["id"] for call in agent_calls["task"]] == ["claude"] and agent_calls["pi"] == []


def test_subtitles_the_mind_map_and_classification_pass_the_agent(data_dir, agent_calls, monkeypatch):
    llm = store.load(data_dir)["llm"]
    fix._ask_model(data_dir, llm, node_exe="node.exe", pi_cli="cli.js")("纠错")
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('<html><body><h1>标题</h1><h2>第一章<span class="section-time">00:00–01:00</span></h2>'
                      "<p>正文。</p></body></html>", encoding="utf-8")
    from prometheus.mindmap import generate
    generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id), llm,
                               node_exe="node.exe", pi_cli="cli.js")
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["classify"](StageContext(data_dir, item_id))
    agents = {call["agent"]["id"] for call in agent_calls["one_shot"]}
    assert len(agent_calls["one_shot"]) >= 3 and agents == {"claude"} and agent_calls["pi"] == []


def test_the_model_test_button_asks_the_agent(client, agent_calls):
    settings = client.get("/api/settings").json()
    settings["llm_profiles"] = {"active": "p1", "items": [CLAUDE]}
    assert client.put("/api/settings", json=settings).status_code == 200
    answer = client.post("/api/settings/test-model").json()
    assert agent_calls["one_shot"] and agent_calls["one_shot"][0]["agent"]["id"] == "claude"
    assert answer["ok"] is True and agent_calls["pi"] == []


def _standard_item(data_dir):
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True, exist_ok=True)
    (work / "transcript.md").write_text("# 转写\n\n[00:00] 你好。\n", encoding="utf-8")
    return item_id, work


def test_the_standard_report_on_another_agent_gets_vras_workspace_and_prompt(data_dir, monkeypatch):
    """VRA's PiRunner only starts Pi: the other Agents get the same staged skill and the same request."""
    item_id, work = _standard_item(data_dir)
    seen = {}

    def fake_task(agent, workspace, prompt, **kwargs):
        seen.update(agent=agent, workspace=workspace, prompt=prompt, **kwargs)
        (workspace / "report.html").write_text("<html><body><h1>报告</h1></body></html>", encoding="utf-8")
        return workspace / "report.html"

    monkeypatch.setattr(runs, "task", fake_task)
    monkeypatch.setattr(workspace_mod, "PiRunner", lambda **kwargs: pytest.fail("PiRunner started for Claude Code"))
    report = workspace_mod.run_report_stage(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                            store.load(data_dir), node_exe="node.exe", pi_cli="cli.js")
    assert report == work / "report.html" and seen["agent"]["id"] == "claude" and seen["expect"] == "report.html"
    assert "video-report skill" in seen["prompt"] and "report-template.html" in seen["prompt"]
    # VRA's own system text for the standard run (vendor pi.py): the report must stand alone
    assert "The supplied transcript is complete; generate a self-contained report.html." in seen["prompt"]
    assert (work / "SKILL.md").is_file() and (work / "modes" / "standard.md").is_file()
    assert (work / "assets" / "report-template.html").is_file() and not (work / "modes" / "brief.md").exists()


def test_an_incomplete_page_from_another_agent_fails_as_it_does_for_pi(data_dir, monkeypatch):
    item_id, _work = _standard_item(data_dir)

    def half_page(agent, workspace, prompt, **kwargs):
        (workspace / "report.html").write_text("<h1>只写了一半", encoding="utf-8")
        return workspace / "report.html"

    monkeypatch.setattr(runs, "task", half_page)
    monkeypatch.setattr(workspace_mod, "PiRunner", lambda **kwargs: pytest.fail("PiRunner started for Claude Code"))
    with pytest.raises(runs.AgentRunError, match="complete HTML"):
        workspace_mod.run_report_stage(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                       store.load(data_dir), node_exe="node.exe", pi_cli="cli.js")


def test_whether_another_agent_sees_images_comes_from_the_profile_not_pis_catalogue(data_dir, monkeypatch):
    """Russell on Codex (2026-09-29) came out without a single screenshot: Pi's catalogue was asked
    whether a model it does not run can see images, and said no."""
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/", figures=1)
    work = paths.work_dir(data_dir, item_id)
    (work / "frames").mkdir(parents=True)
    (work / "frames" / "frames.json").write_text("[]", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(stages_mod.capability, "query_supports_images",
                        lambda *args: pytest.fail("Pi's catalogue asked about another Agent's model"))
    monkeypatch.setattr(stages_mod.workspace_mod, "full_depth", lambda settings: True)
    monkeypatch.setattr(stages_mod.workspace_mod, "run_full_report_stage",
                        lambda *args, **kwargs: seen.update(kwargs) or work / "report.html")
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["report"](StageContext(data_dir, item_id))
    assert seen["figures"] is False  # the profile above says the model cannot see images
    settings = store.load(data_dir)
    settings["llm_profiles"]["items"][0]["supports_images"] = True
    store.save(data_dir, settings)
    stages_mod.build_real_impls(data_dir, runtime=DUMMY_RUNTIME)["report"](StageContext(data_dir, item_id))
    assert seen["figures"] is True


def test_the_profiles_limits_travel_with_the_agent(data_dir):
    settings = store.load(data_dir)
    settings["llm_profiles"]["items"][0].update(context_window=272000, max_tokens=64000)
    store.save(data_dir, settings)
    agent = runs.agent_of(store.load(data_dir)["llm"])
    assert (agent.get("context_window"), agent.get("max_tokens")) == (272000, 64000)
