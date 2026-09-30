"""The two-step 讲清楚 review (PLAN 15.4.11 step 6; after G-Eval's reader-side questions).

First a reader who never saw the video reads one chapter and lists what is unclear, each question
quoting the sentence it is about. Then the chapter's transcript decides, question by question:
the video answers it (the chapter is rewritten once with the answer), it is a term or background
the video takes for granted (a 补充说明 may explain it), or the video does not say (left alone, so
the review never invites invention).
"""

import re

from prometheus.llm.replies import first_json_object
from prometheus.report.evaluation import parse_html
from prometheus.report.markdown_export import report_to_markdown

ANSWERED, BACKGROUND, NOT_THERE = "原文有答案", "术语或背景", "原文没有"
KINDS = (ANSWERED, BACKGROUND, NOT_THERE)
QUESTION_FLOOR = 5.0   # questions a thousand characters of the chapter under which a second reader looks (D-46)
SUPPLEMENT_MIN = 80    # characters of a supplement under which it is a sentence or two (D-46)
PICTURE_REACH = 3      # blocks after the quoted one where the picture asked for may stand
_NOT_WORDY = re.compile(r"[^一-鿿A-Za-z0-9]")
_CJK = re.compile(r"[一-鿿]")
_MEDIA = {"figure", "svg", "img"}
_BLOCKS = {"p", "li", "td", "th", "dd", "dt", "blockquote"}


def _norm(text: str) -> str:
    return _NOT_WORDY.sub("", (text or "").lower())


def reader_prompt(chapter: str) -> str:
    return (
        "你是一位没看过视频的读者：聪明，但对这个领域零基础，不认识这里的术语、人名和书名。"
        "手里只有下面这一章精读。逐段读，列出你看不懂、觉得跳步、或者读完还想追问的地方："
        "第一次出现却没有解释的术语、人名、书名、缩写和外语词（每一个都要列出来）、没交代的前提、"
        "说了结论没说理由、提到却没展开的例子、数字缺单位或口径。"
        "每条照抄你问的那句原文（quote，保持原样），再写出你的问题。"
        "另外，哪里如果配一张图或示意图会更好懂，也列进 pictures：照抄那句原文，写出你想看什么图。"
        "没有疑问就返回空列表。\n"
        '只输出 JSON：{"questions": [{"quote": "…", "question": "…"}], "pictures": [{"quote": "…", "want": "…"}]}\n\n'
        f"本章：\n{report_to_markdown(chapter)}\n"
    )


def needs_second_reader(questions: list, chapter: str) -> bool:
    """Fewer questions for the chapter's length than GPT's readers asked on other videos (PLAN 15.4.14 A)."""
    return len(questions) < QUESTION_FLOOR * len(_CJK.findall(report_to_markdown(chapter))) / 1000


def second_reader_prompt(chapter: str, asked: list) -> str:
    listed = "\n".join(f"- 读到「{q['quote']}」时问：{q['question']}" for q in asked) or "（没有）"
    return (
        "你是第二位没看过视频的读者：聪明，但对这个领域零基础。前一位读者读这一章时已经问过下面这些问题，"
        "不要重复它们。请再逐段读一遍，专门找他没问到、但一个认真的读者还会追问的地方："
        "为什么会这样、凭什么这么说、具体是怎么做到的、能不能举个例子或给个数字、和前面哪一点有什么关系、"
        "反过来会怎样；第一次出现却没有解释的术语、人名、书名也照样列出。"
        "每条照抄你问的那句原文（quote，保持原样），再写出你的问题。"
        "哪里如果配一张图或示意图会更好懂，也列进 pictures：照抄那句原文，写出你想看什么图。"
        "没有新的疑问就返回空列表。\n"
        '只输出 JSON：{"questions": [{"quote": "…", "question": "…"}], "pictures": [{"quote": "…", "want": "…"}]}\n\n'
        f"前一位读者已经问过：\n{listed}\n\n本章：\n{report_to_markdown(chapter)}\n"
    )


def merge(first: list, second: list) -> list:
    """The two readers' questions (or pictures), each asked once."""
    def key(item: dict) -> tuple:
        return _norm(item["quote"]), _norm(item.get("question") or item.get("want") or "")

    seen, merged = {key(item) for item in first}, list(first)
    for item in second:
        if key(item) not in seen:
            seen.add(key(item))
            merged.append(item)
    return merged


def thin_supplements(chapter: str) -> list:
    """Supplements of a sentence or two, without their label (PLAN 15.4.14 B)."""
    found = []
    for node in parse_html(chapter).walk():
        if node.tag == "aside" and "supplement" in node.classes():
            text = node.text(lambda child: "supplement-label" in child.classes()).strip()
            if len(_CJK.findall(text)) < SUPPLEMENT_MIN:
                found.append(text)
    return found


def missing_pictures(chapter: str, pictures: list) -> list:
    """The places the reader wanted a picture with none in the next few blocks (PLAN 15.4.14 C); a place
    rewritten out of the chapter is not asked for again."""
    sequence = []  # document order: the text of each leaf block, or None for a picture
    for node in parse_html(chapter).walk():
        inside = any(ancestor.tag in _MEDIA for ancestor in list(node.ancestors())[1:])
        if node.tag in _MEDIA and not inside:
            sequence.append(None)
        elif node.tag in _BLOCKS and not inside and not any(child.tag in _BLOCKS for child in node.walk()):
            sequence.append(_norm(node.text()))
    missing = []
    for picture in pictures:
        quote = _norm(picture["quote"])
        at = next((index for index, text in enumerate(sequence) if text and quote and quote in text), None)
        if at is None:
            continue
        after, blocks = [], 0
        for item in sequence[at + 1:]:
            if item is not None:
                blocks += 1
                if blocks > PICTURE_REACH:
                    break
            after.append(item)
        if None not in after:
            missing.append(picture)
    return missing


def _quoted(text: str, chapter: str, key: str, field: str) -> list:
    """The reader's items under `key` whose quote really is in the chapter."""
    value = first_json_object(text or "")
    items = value.get(key) if isinstance(value, dict) else None
    body = _norm(report_to_markdown(chapter))
    kept = []
    for item in items if isinstance(items, list) else []:
        item = item if isinstance(item, dict) else {}
        quote, asked = (str(item.get(name) or "").strip() for name in ("quote", field))
        if asked and _norm(quote) and _norm(quote) in body:
            kept.append({"quote": quote, field: asked})
    return kept


def parse_reader(text: str, chapter: str) -> list:
    return _quoted(text, chapter, "questions", "question")


def parse_pictures(text: str, chapter: str) -> list:
    """Where the reader wants a picture (PLAN 15.4.11, 多配图 ③)."""
    return _quoted(text, chapter, "pictures", "want")


def judge_prompt(questions: list, transcript: str) -> str:
    numbered = "\n".join(f"{index}. 读者读到「{q['quote']}」时问：{q['question']}"
                         for index, q in enumerate(questions, 1))
    return (
        "下面是读者读精读的一章时提出的问题，后面附着这一章对应的视频转写。逐条判断：\n"
        f"- {ANSWERED}：转写里讲了答案，answer 用一两句写出答案；\n"
        f"- {BACKGROUND}：转写里没讲，但问的是术语、概念或常识背景，可以用通用知识解释；\n"
        f"- {NOT_THERE}：转写里没讲，也不是术语或背景（例如讲者的私事、没说出的判断）。\n"
        '只输出 JSON：{"verdicts": {"1": {"kind": "原文有答案", "answer": "…"}, "2": {"kind": "术语或背景"}}}\n\n'
        f"问题：\n{numbered}\n\n转写：\n{transcript}\n"
    )


def parse_judge(text: str, count: int) -> list:
    value = first_json_object(text or "")
    found = value.get("verdicts") if isinstance(value, dict) else None
    found = found if isinstance(found, dict) else {}
    verdicts = []
    for index in range(1, count + 1):
        item = found.get(str(index))
        item = item if isinstance(item, dict) else {}
        kind, answer = str(item.get("kind") or "").strip(), str(item.get("answer") or "").strip()
        if kind not in KINDS or (kind == ANSWERED and not answer):
            verdicts.append(None)
        else:
            verdicts.append({"kind": kind, "answer": answer} if kind == ANSWERED else {"kind": kind})
    return verdicts


def fixes(questions: list, verdicts: list, pictures=()) -> list:
    """What to change in the chapter, in the words chapter_checks.feedback_prompt lists."""
    listed = []
    for question, verdict in zip(questions, verdicts):
        kind = (verdict or {}).get("kind")
        asked = f"读者读到「{question['quote']}」时问：{question['question']}"
        if kind == ANSWERED:
            listed.append(f"{asked}。视频里的答案：{verdict['answer']}。把答案写进正文，讲清楚")
        elif kind == BACKGROUND:
            listed.append(f"{asked}。视频里没有讲：在这句附近加一个补充说明（<aside class=\"supplement\">），"
                          "用通用知识解释，不写成讲者的话；按三步写透：它是什么；放在这句话里为什么要紧；"
                          "一个具体例子、数字或出处")
    for picture in pictures:
        listed.append(f"读者读到「{picture['quote']}」时希望有一张图：{picture['want']}。按 depth.md 画一张图示，"
                      "或者用本章候选帧里合适的那张；只画本章正文已经写到的内容")
    return listed
