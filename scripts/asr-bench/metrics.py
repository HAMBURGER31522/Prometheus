"""Scoring for the ASR shoot-out (PLAN 15.4.3).

Chinese: character error rate after converting to simplified script and dropping
punctuation and whitespace. Arabic vs Chinese numerals ("7%" / "百分之七") are
not errors; the edits they would cause are reported apart as ``number_edits``.
English: word error rate after lower-casing and dropping punctuation.
"""

import html
import re
import unicodedata
import warnings

import cn2an
import jiwer
import zhconv

_TIMING = re.compile(r"-->")
_TAG = re.compile(r"<[^>]+>")
# Sound annotations such as (Laughter), [Music], （笑）: not speech.
_ANNOTATION = re.compile(r"\([^)]*\)|\[[^\]]*\]|（[^）]*）")


def subtitle_text(vtt: str, language: str) -> str:
    """The spoken words of a WebVTT file, cue timings and headers removed."""
    lines = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or _TIMING.search(line) or line.isdigit():
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = _ANNOTATION.sub("", html.unescape(_TAG.sub("", line))).strip()
        if line:
            lines.append(line)
    return ("" if language == "zh" else " ").join(lines)


def _is_content(char: str) -> bool:
    return unicodedata.category(char)[0] in "LN"


def normalize_zh(text: str, numbers: bool = False) -> str:
    text = zhconv.convert(text, "zh-cn").lower()
    if numbers:
        with warnings.catch_warnings():  # cn2an warns on idioms like 万一 and leaves them
            warnings.simplefilter("ignore")
            try:
                text = cn2an.transform(text, "cn2an")
            except (ValueError, KeyError):  # cn2an rejects a few malformed numerals
                pass
    return "".join(char for char in text if _is_content(char))


def _char_edits(reference: str, hypothesis: str) -> int:
    if not hypothesis:
        return len(reference)
    out = jiwer.process_characters(reference, hypothesis)
    return out.substitutions + out.deletions + out.insertions


def score_zh(reference: str, hypothesis: str) -> dict:
    raw_ref, raw_hyp = normalize_zh(reference), normalize_zh(hypothesis)
    num_ref, num_hyp = normalize_zh(reference, numbers=True), normalize_zh(hypothesis, numbers=True)
    raw_edits = _char_edits(raw_ref, raw_hyp)
    edits = _char_edits(num_ref, num_hyp)
    return {"cer": edits / len(num_ref), "cer_raw": raw_edits / len(raw_ref),
            "number_edits": raw_edits - edits, "chars": len(num_ref)}


def normalize_en(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return " ".join("".join(char if _is_content(char) else " " for char in text).split())


def score_en(reference: str, hypothesis: str) -> dict:
    ref, hyp = normalize_en(reference), normalize_en(hypothesis)
    return {"wer": jiwer.wer(ref, hyp) if hyp else 1.0, "words": len(ref.split())}


def punctuation_per_100(text: str) -> float:
    """Punctuation marks per 100 spoken characters."""
    marks = sum(1 for char in text if unicodedata.category(char).startswith("P"))
    spoken = sum(1 for char in text if _is_content(char))
    return round(marks * 100 / spoken, 1) if spoken else 0.0
