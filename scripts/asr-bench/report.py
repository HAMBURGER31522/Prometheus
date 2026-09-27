"""Score the bench results against the manual subtitles; print the tables for docs/asr-bench.md.

    python report.py > acceptance-output/asr-bench/tables.md
"""

import difflib
import json
import statistics
import sys
from pathlib import Path

import soundfile

from metrics import normalize_en, normalize_zh, punctuation_per_100, score_en, score_zh, subtitle_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "acceptance-output" / "asr-bench"
ENGINES = ["whisper", "qwen3", "funasr", "bcut"]
NAMES = {"whisper": "faster-whisper turbo", "qwen3": "Qwen3-ASR-1.7B", "funasr": "FunASR paraformer-zh",
         "bcut": "必剪（云端）"}
SUBTITLES = {"zh": "zh.zh-CN.vtt", "en": "en.en.vtt"}


def _reference(sample: str) -> str:
    return subtitle_text((OUT / "samples" / SUBTITLES[sample]).read_text(encoding="utf-8"), sample)


def _excerpts(reference: str, hypothesis: str, sample: str, limit: int = 6) -> list:
    """The first few differing stretches, with a little context on each side."""
    if sample == "zh":
        ref, hyp, join = list(normalize_zh(reference)), list(normalize_zh(hypothesis)), ""
    else:
        ref, hyp, join = normalize_en(reference).split(), normalize_en(hypothesis).split(), " "
    lines = []
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (i2 - i1) + (j2 - j1) < 2:
            continue
        before = join.join(ref[max(0, i1 - 6):i1])
        after = join.join(ref[i2:i2 + 6])
        lines.append(f"参考「{before}【{join.join(ref[i1:i2]) or '∅'}】{after}」→ 识别「【{join.join(hyp[j1:j2]) or '∅'}】」")
        if len(lines) >= limit:
            break
    return lines


def main() -> int:
    for sample in ("zh", "en"):
        duration = soundfile.info(str(OUT / "samples" / f"{sample}.wav")).duration
        reference = _reference(sample)
        metric = "字错率" if sample == "zh" else "词错率"
        print(f"\n### {'中文' if sample == 'zh' else '英文'}样本（{duration / 60:.1f} 分钟）\n")
        extra = "| 数字写法差异 " if sample == "zh" else ""
        print(f"| 引擎 | {metric} {extra}| 加载 | 识别 | 实时率 | 显存峰值 | 分段数 | 中位段长 | 时间戳 | 标点/百字 |")
        print("|---|---|" + ("---|" if sample == "zh" else "") + "---|---|---|---|---|---|---|---|")
        excerpts = {}
        for engine in ENGINES:
            path = OUT / "results" / f"{engine}-{sample}.json"
            if not path.is_file():
                print(f"| {NAMES[engine]} | 未运行 |" + (" |" if sample == "zh" else "") + " | | | | | | | |")
                continue
            result = json.loads(path.read_text(encoding="utf-8"))
            text = result["text"]
            if sample == "zh":
                score = score_zh(reference, text)
                accuracy = f"{score['cer']:.2%} | {score['number_edits']} "
            else:
                score = score_en(reference, text)
                accuracy = f"{score['wer']:.2%} "
            lengths = [s["end"] - s["start"] for s in result["segments"]] or [0]
            vram = f"{result.get('vram_used_mb', 0) / 1024:.1f} GB" if engine != "bcut" else "—"
            print(f"| {NAMES[engine]} | {accuracy}| {result['load_s']:.1f}s | {result['run_s']:.1f}s | "
                  f"{result['run_s'] / duration:.3f} | {vram} | {len(result['segments'])} | "
                  f"{statistics.median(lengths):.1f}s | {result.get('timestamp_unit', '')} | "
                  f"{punctuation_per_100(text):.1f} |")
            excerpts[engine] = _excerpts(reference, text, sample)
        print("\n典型错误摘录（归一化后，参考 = 人工字幕）：\n")
        for engine, lines in excerpts.items():
            print(f"- **{NAMES[engine]}**")
            for line in lines:
                print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
