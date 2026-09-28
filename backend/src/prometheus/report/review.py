"""The two-step 讲清楚 review (PLAN 15.4.11 step 6; after G-Eval's reader-side questions).

First a reader who never saw the video reads one chapter and lists what is unclear, each question
quoting the sentence it is about. Then the chapter's transcript decides, question by question:
the video answers it (the chapter is rewritten once with the answer), it is a term or background
the video takes for granted (a 补充说明 may explain it), or the video does not say (left alone, so
the review never invites invention).
"""

import re

from prometheus.llm.replies import first_json_object
from prometheus.report.markdown_export import report_to_markdown

ANSWERED, BACKGROUND, NOT_THERE = "原文有答案", "术语或背景", "原文没有"
KINDS = (ANSWERED, BACKGROUND, NOT_THERE)
_NOT_WORDY = re.compile(r"[^一-鿿A-Za-z0-9]")


def _norm(text: str) -> str:
    return _NOT_WORDY.sub("", (text or "").lower())


def reader_prompt(chapter: str) -> str:
    return (
        "你是一位没看过视频的读者：聪明，但对这个领域零基础，不认识这里的术语、人名和书名。"
        "手里只有下面这一章精读。逐段读，列出你看不懂、觉得跳步、或者读完还想追问的地方："
        "第一次出现却没有解释的术语、人名、书名、缩写和外语词（每一个都要列出来）、没交代的前提、"
        "说了结论没说理由、提到却没展开的例子、数字缺单位或口径。"
        "每条照抄你问的那句原文（quote，保持原样），再写出你的问题。"
        "没有疑问就返回空列表。\n"
        '只输出 JSON：{"questions": [{"quote": "…", "question": "…"}]}\n\n'
        f"本章：\n{report_to_markdown(chapter)}\n"
    )


def parse_reader(text: str, chapter: str) -> list:
    """The questions whose quote really is in the chapter."""
    value = first_json_object(text or "")
    items = value.get("questions") if isinstance(value, dict) else None
    body = _norm(report_to_markdown(chapter))
    kept = []
    for item in items if isinstance(items, list) else []:
        item = item if isinstance(item, dict) else {}
        quote, question = (str(item.get(key) or "").strip() for key in ("quote", "question"))
        if question and _norm(quote) and _norm(quote) in body:
            kept.append({"quote": quote, "question": question})
    return kept


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


def fixes(questions: list, verdicts: list) -> list:
    """What to change in the chapter, in the words chapter_checks.feedback_prompt lists."""
    listed = []
    for question, verdict in zip(questions, verdicts):
        kind = (verdict or {}).get("kind")
        asked = f"读者读到「{question['quote']}」时问：{question['question']}"
        if kind == ANSWERED:
            listed.append(f"{asked}。视频里的答案：{verdict['answer']}。把答案写进正文，讲清楚")
        elif kind == BACKGROUND:
            listed.append(f"{asked}。视频里没有讲：在这句附近加一个补充说明（<aside class=\"supplement\">），"
                          "用通用知识解释，不写成讲者的话")
    return listed
