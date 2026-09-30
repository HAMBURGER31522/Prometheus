"""Which parts a video gets (PLAN 15.4.15): the report with its mind map, and the subtitles.

Download and transcription always run, so the subtitles' own text is always there; 「字幕」 is their
correction. The mind map is drawn from the report's chapters and never comes without it.
"""

import json

from prometheus.tasks import runner

PARTS = ("report", "subtitles", "mindmap")
ALL = dict.fromkeys(PARTS, True)
DEPTHS = ("full", "standard")
# Skipped without a report (PLAN 15.4.15-3); its mind map is off then too (_valid).
REPORT_STAGES = ("frames", "keypoints", "plan", "report", "finalize")


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


def stages_for(outputs: dict) -> list:
    """The steps a submitted video runs, in the queue's order."""
    skipped = set() if outputs["report"] else set(REPORT_STAGES)
    if not outputs["subtitles"]:
        skipped.add("subtitle_fix")
    if not outputs["mindmap"]:
        skipped.add("mindmap")
    return [stage for stage in runner.STAGES if stage not in skipped]


# 「现在生成」 (PLAN 15.4.15-5): what filling in a part runs on a finished item; its transcript is there.
FILL_STAGES = {
    "report": ("keypoints", "plan", "report", "finalize", "mindmap", "publish"),
    "subtitles": ("subtitle_fix", "publish"),
}
# Before a filled-in report with figures: the video was cleaned after the first run, so only its picture comes back.
PICTURE_STAGES = ("video", "frames")


def fill_stages(part: str, figures: bool) -> list:
    stages = list(FILL_STAGES[part])
    return [*PICTURE_STAGES, *stages] if part == "report" and figures else stages


def filled(outputs: dict, part: str) -> dict:
    """The parts once one is filled in: the report brings its mind map."""
    return {**outputs, part: True, **({"mindmap": True} if part == "report" else {})}


def view(row: dict) -> dict:
    """What the API adds to an item row: its parts, and the steps the console counts."""
    outputs = of(row)
    return {"outputs": outputs, "stages": stages_for(outputs)}
