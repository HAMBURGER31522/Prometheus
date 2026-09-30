"""Which parts a video gets (PLAN 15.4.15): the report with its mind map, and the subtitles.

Download and transcription always run, so the subtitles' own text is always there; 「字幕」 is their
correction. The mind map is drawn from the report's chapters and never comes without it.
"""

import json

PARTS = ("report", "subtitles", "mindmap")
ALL = dict.fromkeys(PARTS, True)
DEPTHS = ("full", "standard")


class Refused(ValueError):
    """A submit that cannot be made; `code` is what the API answers."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _valid(value) -> bool:
    return (isinstance(value, dict) and all(isinstance(value.get(part), bool) for part in PARTS)
            and any(value[part] for part in PARTS) and (value["report"] or not value["mindmap"]))


def of(row: dict) -> dict:
    """The item's parts; NULL (an item from before R7h) is all three."""
    try:
        saved = json.loads(row.get("outputs") or "null")
    except ValueError:
        saved = None
    return {part: saved[part] for part in PARTS} if _valid(saved) else dict(ALL)


def from_submit(body: dict) -> tuple:
    """(outputs, depth) of a submit; a client that sends neither gets all three at the settings' depth (None)."""
    outputs = body.get("outputs", ALL)
    if not _valid(outputs):
        raise Refused("OUTPUTS_INVALID")
    if "depth" in body and body["depth"] not in DEPTHS:
        raise Refused("DEPTH_INVALID")
    return {part: outputs[part] for part in PARTS}, body.get("depth")


def view(row: dict) -> dict:
    """What the API adds to an item row."""
    return {"outputs": of(row)}
