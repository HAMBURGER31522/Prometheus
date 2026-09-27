"""Fill mind map leaves with grounded detail (PLAN 15.4.9). Stub (R7c red)."""


def check_detail(detail: str, summary: str, evidence: str) -> list:
    return []


def enrich_tree(tree: dict, html: str, *, ask) -> tuple:
    return tree, {"coverage": 0.0, "rewrites": 0, "grounding": 0.0, "concrete": 0.0,
                  "chars_by_level": {"root": 0, "theme": 0, "leaf": 0}}
