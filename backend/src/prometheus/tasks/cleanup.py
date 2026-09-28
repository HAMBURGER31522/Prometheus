"""After a successful run keep only what regenerating needs (PLAN 15.4.1).

Media, frames, Pi sessions and the streaming event log are 99% of an item's
footprint (a 104-minute video left 391MB of scratch next to 1.4MB of results).
Failed runs are left untouched so they can be diagnosed.
"""

import shutil
from pathlib import Path

KEEP = frozenset({
    "asr.json", "asr-task.json", "canonical-transcript.jsonl", "input.json",
    "run.trace.jsonl", "source.info.json", "transcript-manifest.json", "transcript.md",
    "segments.json", "segments.raw.json", "segments.fine.json", "mindmap.json",
})


def clean_work_dir(work: Path) -> None:
    work = Path(work)
    if not work.is_dir():
        return
    for path in work.iterdir():
        if path.name in KEEP:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
