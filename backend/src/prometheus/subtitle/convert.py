"""OpenCC t2s for Chinese subtitles (PLAN 8.5, D-20)."""

from functools import lru_cache


@lru_cache(maxsize=1)
def _converter():
    from opencc import OpenCC

    return OpenCC("t2s")


def maybe_simplify(segments: list, language: str) -> list:
    if language != "zh":
        return segments
    converted = []
    for segment in segments:
        row = dict(segment)
        row["text"] = _converter().convert(row["text"])
        converted.append(row)
    return converted


def segments_from_asr(asr_payload: dict) -> list:
    """ASR segments (milliseconds) -> subtitle segments (seconds), simplified for Chinese."""
    segments = [
        {"start": segment["start_ms"] / 1000, "end": segment["end_ms"] / 1000,
         "text": segment["text"]}
        for segment in asr_payload.get("segments", [])
    ]
    return maybe_simplify(segments, asr_payload.get("language"))
