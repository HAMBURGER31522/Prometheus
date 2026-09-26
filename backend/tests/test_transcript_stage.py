"""transcript.md matches the vendor format exactly (golden file, PLAN 8.3)."""

import json
from pathlib import Path

from prometheus.transcribe.transcript import build_transcript_md

FIXTURES = Path(__file__).parent / "fixtures"
METADATA = {
    "title": "示例视频：财政再平衡三十分钟讲透",
    "uploader": "示例UP主",
    "attribution": "示例UP主 · 示例视频：财政再平衡三十分钟讲透",
    "url": "https://www.bilibili.com/video/BV1xJYT6EEYc/",
    "video_id": "BV1xJYT6EEYc",
    "platform": "bilibili",
    "duration_s": 3.2,
}


def test_transcript_md_matches_vendor_golden(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    asr_payload = json.loads((FIXTURES / "asr.local.json").read_text(encoding="utf-8"))
    asr_path = work / "asr.json"
    asr_path.write_text(json.dumps(asr_payload, ensure_ascii=False), encoding="utf-8")

    build_transcript_md(work, asr_path, METADATA)

    produced = (work / "transcript.md").read_text(encoding="utf-8")
    golden = (FIXTURES / "transcript.golden.md").read_text(encoding="utf-8")
    assert produced == golden


def test_transcript_golden_fixture_exists():
    assert (FIXTURES / "transcript.golden.md").is_file()
    assert (FIXTURES / "asr.local.json").is_file()
