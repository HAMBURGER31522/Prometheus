"""Readable folder names for the library (PLAN 15.4.1)."""

from pathlib import Path

UNCATEGORIZED = "未分类"
MAX_NAME = 60

# Characters Windows forbids in names, mapped to their full-width look-alikes.
_FULL_WIDTH = str.maketrans({
    "<": "＜", ">": "＞", ":": "：", '"': "＂", "/": "／",
    "\\": "＼", "|": "｜", "?": "？", "*": "＊",
})


def safe_name(text: str) -> str:
    name = "".join(ch for ch in str(text or "") if ch >= " ").translate(_FULL_WIDTH)
    name = name.strip().rstrip(". ").strip()
    if len(name) > MAX_NAME:
        name = name[:MAX_NAME].rstrip() + "…"
    return name


def category_folder_name(name) -> str:
    return safe_name(name) or UNCATEGORIZED


def item_folder_name(date: str, title: str) -> str:
    return f"{date} {safe_name(title)}".strip()


def unique_child(parent: Path, name: str) -> Path:
    """parent/name, or parent/"name (2)", "(3)"... when the name is taken."""
    parent = Path(parent)
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name} ({number})"
        number += 1
    return candidate
