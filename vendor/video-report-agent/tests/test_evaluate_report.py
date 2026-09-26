import json
import re
from pathlib import Path

from video_report_agent.evaluate_report import evaluate


def test_synthetic_smoke_cases_have_source_anchors():
    root = Path(__file__).parents[1] / "evals/report-review"
    cases = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 3
    for case in cases:
        material = root / case["material"]
        transcript = (material / "transcript.md").read_text(encoding="utf-8")
        ids = set(re.findall(r"^\[([^ |]+) \|", transcript, re.M))
        assert ids
        for check in case["review_checks"]:
            assert set(check["source_ids"]) <= ids
        metadata = json.loads((material / "input.json").read_text(encoding="utf-8"))
        assert set(metadata) <= {"title", "url", "video_id", "uploader", "attribution"}


def test_report_only_ab_preserves_failures_and_does_not_retry(tmp_path, monkeypatch):
    material = tmp_path / "material"
    material.mkdir()
    (material / "transcript.md").write_text("[unit-1 | 0–1s] Original", encoding="utf-8")
    (material / "input.json").write_text('{"title":"test"}', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"cases": [{"id": "sample", "material": "material"}]}), encoding="utf-8",
    )
    calls = []

    class Runner:
        provider, model, thinking = "test", "test", "low"

        def __init__(self, *, review, timeout):
            self.review = review

        async def run(self, run):
            calls.append(self.review)
            assert (run / "transcript.md").read_text(encoding="utf-8") == "[unit-1 | 0–1s] Original"
            assert not (run / "asr.json").exists()
            if not self.review:
                raise RuntimeError("provider failure")
            (run / "report.html").write_text("<html><body>report</body></html>", encoding="utf-8")

    monkeypatch.setattr("video_report_agent.evaluate_report.PiRunner", Runner)
    monkeypatch.setattr("video_report_agent.evaluate_report.inspect_report",
                        lambda run: {"status": "checked", "findings": []})
    output = tmp_path / "experiment"
    rows = evaluate(manifest, output)
    assert calls == [False, True]
    assert rows[0]["status"] == "failed"
    assert rows[1]["review_compliance"] == "missing_or_failed_or_stale_inspection"
    assert json.loads((output / "results.json").read_text(encoding="utf-8")) == rows
    assert (output / "skill-snapshot/SKILL.md").is_file()
    assert (output / "runtime-snapshot/report_content.py").is_file()
