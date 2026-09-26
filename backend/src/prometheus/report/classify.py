"""Auto classification via one-shot text call (PLAN 8.6)."""

FORBIDDEN = {"其他", "综合", "杂项"}


def parse_category_response(text: str):
    raise NotImplementedError


def validate_category(name: str, existing: list) -> bool:
    raise NotImplementedError


def build_classify_prompt(title: str, intro: str, h2_titles: list, existing: list) -> str:
    raise NotImplementedError


def classify_report(work_dir, title: str, intro: str, h2_titles: list, existing: list, *,
                    one_shot=None, **one_shot_kwargs) -> str:
    raise NotImplementedError
