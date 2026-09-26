"""Subtitle segment formatting (PLAN 8.5; OpenCC and >1h handling in M3)."""

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
        blocks.append(f"{index}\n{start} --> {end}\n{segment['text']}\n")
    return "\n".join(blocks)


def to_txt(segments) -> str:
    lines = []
    for segment in segments:
        total = int(segment["start"])
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        lines.append(f"[{hours:02d}:{minutes:02d}:{secs:02d}] {segment['text']}")
    return "\n".join(lines) + "\n"
