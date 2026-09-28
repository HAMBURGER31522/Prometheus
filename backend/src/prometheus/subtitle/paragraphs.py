"""Subtitle paragraphs of 10–15 seconds (PLAN 15.4.10)."""


def group_segments(segments: list) -> list:
    return [dict(segment) for segment in segments]


def group_pair(shown: list, raw: list) -> tuple:
    return group_segments(shown), group_segments(raw)
