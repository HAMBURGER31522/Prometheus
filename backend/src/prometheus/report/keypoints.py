"""The key-point ledger (PLAN 15.4.11). Stub."""


def keypoint_prompt(block: list) -> str:
    return ""


def parse_points(text: str, block: list) -> tuple:
    return [], [], []


def unassigned(block: list, points: list, skips: list, *, min_seconds: float = 30) -> list:
    return []


def build_ledger(units: list, ask, *, seconds: float = 300, workers: int = 3) -> dict:
    return {"points": [], "skips": [], "problems": [], "uncovered": []}


def ledger_markdown(ledger: dict) -> str:
    return ""


def write_parts(units: list, folder, *, seconds: float = 300) -> list:
    return []
