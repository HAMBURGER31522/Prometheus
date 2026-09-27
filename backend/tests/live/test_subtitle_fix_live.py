"""E10 (PLAN 15.3): subtitle correction on the R5 Chinese sample, scored against the uploader's subtitles.

Inputs are the R5 bench outputs under acceptance-output/asr-bench (not committed; run
scripts/asr-bench first). No report is passed as reference here, so this measures what
context alone fixes. Costs roughly 20k tokens on the configured model.

Credentials: PROMETHEUS_TEST_LLM_KEY; optional PROMETHEUS_TEST_LLM_BASE_URL,
PROMETHEUS_TEST_LLM_MODEL, PROMETHEUS_TEST_LLM_PROTOCOL (openai | anthropic).
"""

import json
import os
import unicodedata
from pathlib import Path

import pytest
from prometheus import paths
from prometheus.llm import pi_models
from prometheus.settings import store
from prometheus.subtitle import fix
from prometheus.subtitle.vtt import parse_vtt

pytestmark = pytest.mark.live

BENCH = Path(os.getenv("PROMETHEUS_TEST_ASR_BENCH", "acceptance-output/asr-bench")).resolve()
KEY = os.getenv("PROMETHEUS_TEST_LLM_KEY", "")
BASE_URL = os.getenv("PROMETHEUS_TEST_LLM_BASE_URL", "https://oapi.firedog.dev/v1")
MODEL = os.getenv("PROMETHEUS_TEST_LLM_MODEL", "gpt-6-sol")
PROTOCOL = os.getenv("PROMETHEUS_TEST_LLM_PROTOCOL", "openai")
NODE = os.getenv("PROMETHEUS_NODE") or "node"
PI_CLI = os.getenv("PROMETHEUS_PI_CLI") or (
    "E:/tools/Prometheus-Desktop/pi/node_modules/@earendil-works"
    "/pi-coding-agent/dist/bundle/cli.js"
)

requires_key = pytest.mark.skipif(not KEY, reason="PROMETHEUS_TEST_LLM_KEY 未设置")


def _cer(reference: list, text: str) -> float:
    return fix._distance(reference, fix._letters(text)) / len(reference)


def _punctuation_per_100(text: str) -> float:
    marks = sum(1 for char in text if unicodedata.category(char).startswith("P"))
    return marks * 100 / max(1, len(fix._letters(text)))


@requires_key
@pytest.mark.parametrize("engine", ["whisper", "bcut"])
def test_correction_lowers_cer_and_keeps_every_segment(engine, tmp_path):
    result_file = BENCH / "results" / f"{engine}-zh.json"
    if not result_file.is_file():
        pytest.skip(f"{result_file} 不存在：先运行 scripts/asr-bench")
    segments = json.loads(result_file.read_text(encoding="utf-8"))["segments"]
    reference = fix._letters("".join(
        cue["text"] for cue in parse_vtt((BENCH / "samples" / "zh.zh-CN.vtt").read_text(encoding="utf-8"))))

    data_dir = paths.init_data_dir(tmp_path / "data")
    custom = {"base_url": BASE_URL, "supports_images": False, "protocol": PROTOCOL}
    llm = {"provider": "custom", "model": MODEL, "api_key": KEY, "thinking": "low", "custom": custom}
    store.save(data_dir, {**store.load(data_dir), "llm": llm})
    pi_models.ensure_models_json(data_dir)
    pi_models.apply_custom_provider(data_dir, custom)

    fixed, stats = fix.fix_segments(segments, "", human=False,
                                    ask=fix._ask_model(data_dir, llm, node_exe=NODE, pi_cli=PI_CLI))
    before_text = "".join(s["text"] for s in segments)
    after_text = "".join(s["text"] for s in fixed)
    summary = {
        "engine": engine, "model": MODEL, "segments": len(segments), **stats,
        "cer_before": round(_cer(reference, before_text), 4), "cer_after": round(_cer(reference, after_text), 4),
        "punctuation_before": round(_punctuation_per_100(before_text), 1),
        "punctuation_after": round(_punctuation_per_100(after_text), 1),
    }
    (BENCH / "results" / f"fix-{engine}-zh.json").write_text(
        json.dumps({"summary": summary, "segments": fixed}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summary)

    assert [(s["start"], s["end"]) for s in fixed] == [(s["start"], s["end"]) for s in segments]
    assert summary["cer_after"] < summary["cer_before"], summary
    if engine == "bcut":
        assert summary["punctuation_after"] >= 5, summary
