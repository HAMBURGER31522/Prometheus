"""M4 report stage: workspace assembly and Pi command construction (PLAN 8.6)."""

import json
import sys
from pathlib import Path

from prometheus.report.workspace import build_input_json, build_runner_kwargs

ROW = {
    "id": "a" * 32, "platform": "bilibili", "video_id": "BV1xJYT6EEYc",
    "source_url": "https://www.bilibili.com/video/BV1xJYT6EEYc/",
    "source_title": "财政再平衡", "uploader": "示例UP主", "duration_s": 498.4,
}
SETTINGS = {
    "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "sk-test",
            "thinking": "low", "custom": {"base_url": "", "supports_images": False}},
}

FAKE_PI = """#!/usr/bin/env python3
import json,sys
open("received-stdin.txt", "wb").write(sys.stdin.buffer.read())
json.loads(sys.stdin.readline())
open("report.html", "w").write(
    "<html><head></head><body><h1>财政再平衡</h1><p>正文</p></body></html>")
print(json.dumps({"type":"message_end","message":{"role":"assistant","stopReason":"stop"}}))
print(json.dumps({"type":"agent_settled"}),flush=True)
"""


def make_fake_pi_cmd(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_pi_script.py"
    script.write_text(body, encoding="utf-8")
    launcher = tmp_path / "fake-pi.cmd"
    launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    return launcher


def test_input_json_fields_match_plan():
    payload = build_input_json(ROW)
    assert payload["platform"] == "Bilibili"
    assert payload["report_mode"] == "standard"
    assert payload["title"] == "财政再平衡"
    assert payload["uploader"] == "示例UP主"
    assert payload["url"] == ROW["source_url"]
    assert payload["video_id"] == "BV1xJYT6EEYc"
    assert payload["attribution"].startswith("Bilibili；示例UP主；《财政再平衡》")


def test_runner_kwargs_tools_and_prefix():
    kwargs = build_runner_kwargs(ROW, SETTINGS, "node.exe", "cli.js", figures=False,
                                 model_supports_images=False)
    assert kwargs["command_prefix"] == ["node.exe", "cli.js"]
    assert kwargs["tools"] == "read,write,edit,powershell"
    assert "bash" not in kwargs["tools"]
    assert kwargs["timeout"] == 1800 + 600 * 1  # 498s -> ceil(1) hour


def test_runner_kwargs_figures_require_image_support():
    off = build_runner_kwargs(ROW, SETTINGS, "n", "c", figures=True,
                              model_supports_images=False)
    assert "figures.md" not in (off["extra_prompt"] or "")
    assert not off["extra_files"]
    on = build_runner_kwargs(ROW, SETTINGS, "n", "c", figures=True,
                             model_supports_images=True)
    assert "figures.md" in on["extra_prompt"]
    assert Path(on["extra_files"][0]).name == "figures.md"


def test_report_stage_runs_pi_and_writes_input_json(tmp_path, monkeypatch):
    import asyncio

    from prometheus import paths
    from prometheus.report import workspace as workspace_mod

    data_dir = paths.init_data_dir(tmp_path / "data")
    item_id = "a" * 32
    work = paths.work_dir(data_dir, item_id)
    work.mkdir(parents=True)
    (work / "transcript.md").write_text("# 样本\n\n[unit-000001 | 0.000-1.000s] 内容", encoding="utf-8")
    (work / "source.info.json").write_text(json.dumps({"description": "简介"}), encoding="utf-8")
    (work / "input.json").unlink(missing_ok=True)

    executable = make_fake_pi_cmd(tmp_path, FAKE_PI)
    seen = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def run(self, work_dir):
            return asyncio.Event().loop if False else _fake_run(work_dir)

    def _fake_run(work_dir):
        (work_dir / "report.html").write_text(
            "<html><head></head><body><h1>财政再平衡</h1><p>正文</p></body></html>",
            encoding="utf-8",
        )
        return work_dir / "report.html"

    monkeypatch.setattr(workspace_mod, "PiRunner", FakeRunner)
    report = workspace_mod.run_report_stage(
        data_dir, item_id, ROW, SETTINGS, node_exe="node.exe", pi_cli="cli.js",
    )
    assert report.is_file()
    payload = json.loads((work / "input.json").read_text(encoding="utf-8"))
    assert payload["platform"] == "Bilibili" and payload["report_mode"] == "standard"
    assert seen["command_prefix"] == ["node.exe", "cli.js"]
    assert seen["agent_dir"] == paths.pi_config_dir(data_dir)
