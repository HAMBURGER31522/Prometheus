"""Subtitle segment formatting (PLAN 8.5; OpenCC and >1h handling in M3). A segment with a
Chinese translation (`zh`, PLAN 15.4.9) exports as two lines: the original, then the translation."""

from math import floor as _floor


def _timestamp(seconds: float, decimal: str) -> str:
    total = _floor(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = round((seconds - total) * 1000)
    if millis == 1000:
        millis = 0
        total += 1
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal}{millis:03d}"


def to_srt(segments) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _timestamp(segment["start"], ",")
        end = _timestamp(segment["end"], ",")
        text = segment["text"] + (f"\n{segment['zh']}" if segment.get("zh") else "")
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def to_txt(segments) -> str:
    lines = []
    for segment in segments:
        total = int(segment["start"])
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        lines.append(f"[{hours:02d}:{minutes:02d}:{secs:02d}] {segment['text']}")
        if segment.get("zh"):
            lines.append(" " * len("[00:00:00] ") + segment["zh"])
    return "\n".join(lines) + "\n"
