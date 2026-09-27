"""WebVTT to subtitle segments (PLAN 15.4.4): platform subtitles take the place of ASR."""

import html
import re

_TIMING = re.compile(r"^((?:\d+:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d+:)?\d{2}:\d{2}\.\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _seconds(stamp: str) -> float:
    parts = [float(part) for part in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return round(hours * 3600 + minutes * 60 + seconds, 3)


def parse_vtt(text: str) -> list:
    """``[{"start": s, "end": s, "text": str}]``; cue lines joined with spaces, tags dropped."""
    segments, cue, lines = [], None, []

    def close():
        body = " ".join(lines).strip()
        if cue is not None and body:
            segments.append({"start": cue[0], "end": cue[1], "text": body})

    for raw in text.splitlines():
        line = raw.strip()
        timing = _TIMING.match(line)
        if timing:
            close()
            cue, lines = (_seconds(timing.group(1)), _seconds(timing.group(2))), []
        elif not line:
            close()
            cue, lines = None, []
        elif cue is not None:
            lines.append(html.unescape(_TAG.sub("", line)).strip())
    close()
    return segments
