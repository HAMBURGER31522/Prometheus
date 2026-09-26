"""Auto classification via one-shot text call (PLAN 8.6)."""

import json
import re

FORBIDDEN = {"其他", "综合", "杂项"}
_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_category_response(text: str):
    match = _JSON_RE.search(text or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    name = payload.get("category")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def validate_category(name: str, existing: list) -> bool:
    if name in existing:
        return True
    stripped = name.strip()
    if not 2 <= len(stripped) <= 8:
        return False
    if stripped in FORBIDDEN:
        return False
    return all("\u4e00" <= ch <= "\u9fff" for ch in stripped)


def build_classify_prompt(title: str, intro: str, h2_titles: list, existing: list) -> str:
    names = "、".join(existing[:50]) or "（无）"
    chapters = "；".join(h2_titles)
    return (
        "为以下报告选择一个分类。优先从已有分类中选择；都不合适时提出一个新分类。\n"
        f"已有分类：{names}\n"
        f"报告标题：{title}\n"
        f"导语：{intro}\n"
        f"章节标题：{chapters}\n"
        '只输出 JSON：{"category": "名称"}。'
        "新分类名必须是 2-8 个汉字的名词短语，不能用「其他 / 综合 / 杂项」这类名字。"
    )


def classify_report(work_dir, title: str, intro: str, h2_titles: list, existing: list, *,
                    one_shot, **one_shot_kwargs) -> str:
    """Parse and validate the model's answer; retry once, then fall back."""
    prompt = build_classify_prompt(title, intro, h2_titles, existing)
    for _ in range(2):
        text = one_shot(work_dir, prompt=prompt, **one_shot_kwargs)
        name = parse_category_response(text)
        if name and validate_category(name, existing):
            return name
    return "未分类"
