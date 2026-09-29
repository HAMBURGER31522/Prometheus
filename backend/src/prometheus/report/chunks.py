"""The canonical transcript in ~5-minute blocks (PLAN 15.4.11): closed-book questions are asked
per block, and the key-point ledger reads one block per model call."""

import json
from pathlib import Path


def load_units(path) -> list:
    """Rows of a cache ``canonical-transcript.jsonl`` ({unit_id, start_ms, end_ms, canonical_text, ...})."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def chunk_units(units: list, *, seconds: float = 300) -> list:
    """Consecutive blocks on unit boundaries: a new block starts once a unit begins `seconds` after
    the block's first one; a tail shorter than a third of a block joins the block before it."""
    limit = seconds * 1000
    blocks: list = []
    for unit in units:
        if blocks and unit["start_ms"] - blocks[-1][0]["start_ms"] < limit:
            blocks[-1].append(unit)
        else:
            blocks.append([unit])
    if len(blocks) > 1 and blocks[-1][-1]["end_ms"] - blocks[-1][0]["start_ms"] < limit / 3:
        blocks[-2].extend(blocks.pop())
    return blocks
