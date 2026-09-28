"""Report evaluation (PLAN 15.4.11). Stub."""


def component_counts(html: str) -> dict:
    return {"total": 0, "figure": 0, "img": 0, "svg": 0, "table": 0, "steps": 0, "callout": 0, "cards": 0,
            "comparison": 0}


def citation_coverage(html: str, units: list) -> dict:
    return {"covered": 0, "total": 0, "share": 0.0, "longest_gap_min": 0.0}


def points_coverage(html: str, points: list, skipped=frozenset()):
    return 0.0


def chapter_density(html: str) -> list:
    return []


def report_sentences(html: str, units: list) -> list:
    return []


def sample_sentences(sentences: list, count: int, *, seed: int = 7) -> list:
    return []


def report_supplements(html: str, units: list) -> list:
    return []


def question_prompt(block: list) -> str:
    return ""


def parse_questions(text: str, block_ids: list) -> tuple:
    return [], []


def parse_answers(text: str, count: int) -> list:
    return []


def parse_grades(text: str, count: int) -> list:
    return []


def qa_score(grades: list) -> dict:
    return {}


def estimate_tokens(text: str) -> int:
    return 0


def estimate_cost(calls: list) -> dict:
    return {}


def evaluate_report(units: list, html: str, questions_file, ask, *, points=None, skipped=frozenset()) -> dict:
    return {}
