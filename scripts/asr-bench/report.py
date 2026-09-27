"""Score the bench results against the manual subtitles; print the tables for docs/asr-bench.md.

    python report.py > acceptance-output/asr-bench/tables.md
"""

import difflib
import json
import statistics
import sys
from pathlib import Path

import jiwer
import soundfile
from metrics import (
    normalize_en,
    normalize_zh,
    punctuation_per_100,
    score_en,
    score_zh,
    subtitle_text,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "acceptance-output" / "asr-bench"
ENGINES = ["whisper", "qwen3", "qwen3-seq", "funasr", "bcut"]
NAMES = {"whisper": "faster-whisper turbo", "qwen3": "Qwen3-ASR-1.7B（同时加载）",
         "qwen3-seq": "Qwen3-ASR-1.7B（先后加载）", "funasr": "FunASR paraformer-zh",
         "bcut": "必剪（云端）"}
SUBTITLES = {"zh": "zh.zh-CN.vtt", "en": "en.en.vtt"}


def _reference(sample: str) -> str:
    return subtitle_text((OUT / "samples" / SUBTITLES[sample]).read_text(encoding="utf-8"), sample)


def _units(reference: str, hypothesis: str, sample: str):
    """Normalized reference/hypothesis units (characters or words) and their joiner."""
    if sample == "zh":
        return list(normalize_zh(reference, numbers=True)), list(normalize_zh(hypothesis, numbers=True)), ""
    return normalize_en(reference).split(), normalize_en(hypothesis).split(), " "


def _sdi(reference: str, hypothesis: str, sample: str) -> str:
    ref, hyp, join = _units(reference, hypothesis, sample)
    process = jiwer.process_characters if sample == "zh" else jiwer.process_words
    out = process(join.join(ref), join.join(hyp))
    return f"{out.substitutions}/{out.deletions}/{out.insertions}"


def _excerpts(reference: str, hypothesis: str, sample: str, limit: int = 8) -> list:
    """The first misheard stretches (substitutions only: deletions and insertions are
    mostly where the subtitles and the speech disagree), with context."""
    ref, hyp, join = _units(reference, hypothesis, sample)
    lines = []
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace" or max(i2 - i1, j2 - j1) > 12:
            continue
        before = join.join(ref[max(0, i1 - 6):i1])
        after = join.join(ref[i2:i2 + 6])
        lines.append(f"参考「{before}【{join.join(ref[i1:i2]) or '∅'}】{after}」→ 识别「【{join.join(hyp[j1:j2]) or '∅'}】」")
        if len(lines) >= limit:
            break
    return lines


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the console is cp936; redirect to a file to read
    for sample in ("zh", "en"):
        duration = soundfile.info(str(OUT / "samples" / f"{sample}.wav")).duration
        reference = _reference(sample)
        metric = "字错率" if sample == "zh" else "词错率"
        print(f"\n### {'中文' if sample == 'zh' else '英文'}样本（{duration / 60:.1f} 分钟）\n")
        extra = "| 数字写法差异 " if sample == "zh" else ""
        print(f"| 引擎 | {metric} | 替换/删除/插入 {extra}| 加载 | 识别 | 实时率 | 显存增量 | 分段数 | 中位段长 "
              "| 时间戳 | 标点/百字 |")
        print("|---|---|---|" + ("---|" if sample == "zh" else "") + "---|---|---|---|---|---|---|---|")
        excerpts = {}
        for engine in ENGINES:
            path = OUT / "results" / f"{engine}-{sample}.json"
            if not path.is_file():
                print(f"| {NAMES[engine]} | 未运行 | |" + (" |" if sample == "zh" else "") + " | | | | | | | |")
                continue
            result = json.loads(path.read_text(encoding="utf-8"))
            text = result["text"]
            if sample == "zh":
                score = score_zh(reference, text)
                accuracy = f"{score['cer']:.2%} | {_sdi(reference, text, sample)} | {score['number_edits']} "
            else:
                score = score_en(reference, text)
                accuracy = f"{score['wer']:.2%} | {_sdi(reference, text, sample)} "
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
