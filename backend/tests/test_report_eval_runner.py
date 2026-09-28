"""scripts/report-eval/run.py end to end with --fake (PLAN 15.4.11): no model is called."""

import importlib.util
import json
from pathlib import Path

from prometheus import paths
from prometheus.library import db
from prometheus.library import items as items_store

RUNNER = Path(__file__).parents[2] / "scripts" / "report-eval" / "run.py"
REPORT = """<html><head></head><body><main class="paper"><header class="intro"><h1>手冲咖啡</h1></header>
<section id="s1"><h2><span class="section-title">变量</span><span class="section-time">00:00–00:10</span></h2>
<p data-source-units="unit-000001 unit-000002">水温决定了苦味和酸味的平衡。</p></section></main></body></html>"""


def load_runner():
    spec = importlib.util.spec_from_file_location("report_eval_run", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data_dir_with_item(tmp_path):
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    folder = "测试/2026-09-28 手冲咖啡"
    items_store.update_item(data_dir, item_id, status="done", report_title="手冲咖啡", library_path=folder)
    (data_dir / folder).mkdir(parents=True)
    (data_dir / folder / paths.LIBRARY_FILES["html"]).write_bytes(REPORT.encode("utf-8"))
    cache = paths.cache_dir(data_dir, item_id)
    cache.mkdir(parents=True, exist_ok=True)
    rows = [{"unit_id": f"unit-{i:06d}", "start_ms": (i - 1) * 1000, "end_ms": i * 1000,
             "canonical_text": f"原话{i}。"} for i in range(1, 11)]
    (cache / "canonical-transcript.jsonl").write_bytes(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8"))
    return data_dir, item_id


def test_a_fake_run_writes_questions_results_and_a_summary(tmp_path):
    data_dir, item_id = data_dir_with_item(tmp_path)
    out = tmp_path / "out"
    code = load_runner().main([str(data_dir), "--out", str(out), "--label", "old", "--fake"])
    assert code == 0
    assert (out / "questions" / f"{item_id}.json").is_file()
    result = json.loads((out / "results" / f"{item_id}-old.json").read_text(encoding="utf-8"))
    assert result["title"] == "手冲咖啡" and result["label"] == "old"
    assert result["qa"]["total"] >= 1
    summary = (out / "summary-old.md").read_text(encoding="utf-8")
    assert "手冲咖啡" in summary and "闭卷问答" in summary and "估算" in summary


def test_another_report_of_the_item_meets_the_same_questions(tmp_path):
    data_dir, item_id = data_dir_with_item(tmp_path)
    out = tmp_path / "out"
    runner = load_runner()
    assert runner.main([str(data_dir), "--out", str(out), "--label", "old", "--fake"]) == 0
    before = (out / "questions" / f"{item_id}.json").read_bytes()
    other = tmp_path / "new.html"
    other.write_bytes(REPORT.replace("水温", "粉水比").encode("utf-8"))
    assert runner.main([str(data_dir), "--out", str(out), "--label", "new", "--fake",
                        "--report", f"{item_id}={other}"]) == 0
    assert (out / "questions" / f"{item_id}.json").read_bytes() == before
    new = json.loads((out / "results" / f"{item_id}-new.json").read_text(encoding="utf-8"))
    assert new["report"] == str(other)


def test_a_full_report_is_measured_against_its_ledger_with_the_plans_skips_left_out(tmp_path):
    data_dir, item_id = data_dir_with_item(tmp_path)
    cache = paths.cache_dir(data_dir, item_id)
    ledger = {"points": [{"id": "K001", "units": ["unit-000001", "unit-000002"]},
                         {"id": "K002", "units": ["unit-000009", "unit-000010"]}], "skips": []}
    (cache / "keypoints.json").write_bytes(json.dumps(ledger).encode("utf-8"))
    (cache / "coverage.json").write_bytes(json.dumps({"skipped": [{"id": "K002", "reason": "广告推广"}]},
                                                     ensure_ascii=False).encode("utf-8"))
    marked = tmp_path / "marked.html"
    marked.write_bytes(REPORT.replace("<p data-source-units", '<p data-points="K001" data-source-units').encode("utf-8"))
    out = tmp_path / "out"
    assert load_runner().main([str(data_dir), "--out", str(out), "--label", "new", "--fake",
                               "--report", f"{item_id}={marked}"]) == 0
    result = json.loads((out / "results" / f"{item_id}-new.json").read_text(encoding="utf-8"))
    assert result["points_coverage"] == 1.0  # K002 was skipped for a reason
    assert result["time"]["excluded"] == 2
    summary = (out / "summary-new.md").read_text(encoding="utf-8")
    assert "时间覆盖" in summary and "跳过 1 条" in summary


def test_questions_only_stops_after_the_questions(tmp_path):
    data_dir, item_id = data_dir_with_item(tmp_path)
    out = tmp_path / "out"
    assert load_runner().main([str(data_dir), "--out", str(out), "--questions-only", "--fake"]) == 0
    assert (out / "questions" / f"{item_id}.json").is_file()
    assert not (out / "results").exists()


def test_a_relative_data_dir_still_gives_pi_an_absolute_config_dir(tmp_path, monkeypatch):
    """Pi runs in another working directory: a relative config dir made it lose the custom provider."""
    data_dir, _ = data_dir_with_item(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = load_runner()
    seen = {}
    monkeypatch.setattr(runner.runtime_mod, "resolve", lambda _: type("R", (), {"node": "n", "pi_cli": "c"})())
    monkeypatch.setattr(runner.one_shot, "run_one_shot", lambda work, **kwargs: seen.update(kwargs, work=work) or "{}")
    ask = runner.model_ask(Path("data"), Path("out") / "work", "low")
    ask("提示词")
    assert Path(seen["agent_dir"]).is_absolute()
    assert Path(seen["work"]).is_absolute()
    assert Path(seen["agent_dir"]) == paths.pi_config_dir(data_dir.resolve())
