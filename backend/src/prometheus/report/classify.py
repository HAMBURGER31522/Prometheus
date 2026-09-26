"""Auto classification via one-shot text call (PLAN 8.6)."""

import json
import re

FORBIDDEN = {"其他", "综合", "杂项"}
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


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


MAX_TAGS = 5
MAX_TAG_CHARS = 12
MAX_DESCRIPTION_CHARS = 80


def build_classify_prompt(title: str, intro: str, h2_titles: list, existing: list) -> str:
    names = "、".join(existing[:50]) or "（无）"
    chapters = "；".join(h2_titles)
    return (
        "为以下报告选择一个分类，并给出标签和一句话摘要。优先从已有分类中选择；都不合适时提出一个新分类。\n"
        f"已有分类：{names}\n"
        f"报告标题：{title}\n"
        f"导语：{intro}\n"
        f"章节标题：{chapters}\n"
        '只输出 JSON：{"category": "名称", "tags": ["标签1", "标签2", "标签3"], "description": "一句话摘要"}。'
        "新分类名必须是 2-8 个汉字的名词短语，不能用「其他 / 综合 / 杂项」这类名字。"
        f"tags 给 3-5 个，每个不超过 {MAX_TAG_CHARS} 个字，是内容里的核心概念或人物；"
        f"description 是一句话，不超过 {MAX_DESCRIPTION_CHARS} 个字，直接写视频讲了什么。"
    )


def _clean_tags(value) -> list:
    tags: list = []
    for tag in value if isinstance(value, list) else []:
        tag = str(tag).strip()
        if tag and len(tag) <= MAX_TAG_CHARS and tag not in tags:
            tags.append(tag)
    return tags[:MAX_TAGS]


def _first_sentence(text: str) -> str:
    match = re.match(r"(.+?[。！？!?])", (text or "").strip(), re.DOTALL)
    sentence = (match.group(1) if match else (text or "")).strip()
    return sentence[:MAX_DESCRIPTION_CHARS]


def classify_item(work_dir, title: str, intro: str, h2_titles: list, existing: list, *,
                  one_shot, **one_shot_kwargs) -> dict:
    """Category (validated, one retry, then 未分类) plus best-effort tags and description."""
    prompt = build_classify_prompt(title, intro, h2_titles, existing)
    payload: dict = {}
    category = "未分类"
    for _ in range(2):
        text = one_shot(work_dir, prompt=prompt, **one_shot_kwargs)
        name = parse_category_response(text)
        if name and validate_category(name, existing):
            category = name
            match = _JSON_RE.search(text or "")
            try:
                payload = json.loads(match.group(0)) if match else {}
            except ValueError:
                payload = {}
            break
    description = str(payload.get("description") or "").strip()
    if not description or len(description) > MAX_DESCRIPTION_CHARS:
        description = _first_sentence(intro)
    return {"category": category, "tags": _clean_tags(payload.get("tags")),
            "description": description}


def classify_report(work_dir, title: str, intro: str, h2_titles: list, existing: list, *,
                    one_shot, **one_shot_kwargs) -> str:
    """Just the category name (kept for callers that need nothing else)."""
    return classify_item(work_dir, title, intro, h2_titles, existing,
                         one_shot=one_shot, **one_shot_kwargs)["category"]
