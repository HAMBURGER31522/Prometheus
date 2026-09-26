"""Readable folder names for the library (PLAN 15.4.1)."""

from pathlib import Path


def safe_name(text: str) -> str:
    return text


def category_folder_name(name) -> str:
    return name


def item_folder_name(date: str, title: str) -> str:
    return title


def unique_child(parent: Path, name: str) -> Path:
    return Path(parent) / name
