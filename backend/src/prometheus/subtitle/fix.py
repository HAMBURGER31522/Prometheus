"""Subtitle correction after the report (PLAN 15.4.6, D-37). Stub (R6b red)."""

MAX_REFERENCE = 12000
SEGMENTS_MARK = "字幕分段（JSON）：\n"


def accept(original: str, corrected: str) -> bool:
    return False


def parse_reply(text: str):
    return None


def build_prompt(batch: dict, reference: str, *, human: bool) -> str:
    return SEGMENTS_MARK + "{}"


def fix_segments(segments: list, reference: str, *, human: bool, ask) -> tuple:
    return [dict(s) for s in segments], {"changed": 0, "rejected": 0, "failed_batches": 0}


def _ask_model(data_dir, llm: dict, *, node_exe: str, pi_cli: str):
    raise NotImplementedError


def fix_for_item(data_dir, item_id: str, row: dict, llm: dict, *, node_exe: str, pi_cli: str) -> bool:
    return False
