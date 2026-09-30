"""「标准」精读 (PLAN 15.4.15-10): VRA's one-go report, an editor's-viewpoint pass per chapter, a jump TOC."""

from prometheus.report import viewpoints


def chapters(html: str) -> list:
    return []


def add_nav(html: str) -> str:
    return html


def add_viewpoints(work, run_pi, *, verify_links, progress, gate=None) -> dict:
    return dict.fromkeys(viewpoints.STATS, 0)
