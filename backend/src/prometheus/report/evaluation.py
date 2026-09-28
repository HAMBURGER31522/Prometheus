"""Report evaluation (PLAN 15.4.11 「评测」): how complete and how faithful a 精读 report is.

- Closed-book questions: 4 per ~5-minute block of the transcript, made from the transcript only
  and kept in a file, so an old and a new report of an item meet exactly the same questions;
  the report alone answers them, then each answer is graded against the reference.
- Faithfulness: 40 sentences sampled from the body (never from 「补充说明」) are judged against the
  transcript units they cite; supplements are only checked for contradicting the video.
- Program metrics: citation and key-point coverage, characters per source minute, components.

The model is injected as ``ask(prompt) -> reply``; nothing here calls one.
"""

import json
import math
import random
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

from prometheus.llm.replies import first_json_object
from prometheus.report.chunks import chunk_units
from prometheus.report.markdown_export import report_to_markdown

QUESTIONS_PER_BLOCK = 4
GRADES = ("正确", "部分正确", "未提及", "错误")
FAITHFUL = ("有依据", "部分有依据", "无依据")
CONTRADICTION = ("矛盾", "不矛盾")
# The components the Standard template defines (assets/report-template.html) plus plain HTML ones.
COMPONENT_TAGS = ("figure", "img", "svg", "table")
COMPONENT_CLASSES = ("cards", "comparison", "steps", "callout", "keyline", "tiles", "stats", "bars",
                     "categories", "cycle-map")
# Anthropic's list price for claude-opus-4-8 in Pi's catalogue, USD per million tokens.
PRICE_IN, PRICE_OUT = 5.0, 25.0

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_HIDDEN = {"script", "style"}
_BLOCKS = {"p", "li", "td", "th", "dd", "dt", "blockquote"}
_CJK = re.compile(r"[一-鿿]")
_WORDY = re.compile(r"[一-鿿A-Za-z0-9]")
_SENTENCE_END = re.compile(r"(?<=[。！？!?])")
_RANGE = re.compile(r"(\d{1,2}(?::\d{2}){1,2})\s*[–—~-]\s*(\d{1,2}(?::\d{2}){1,2})")
MIN_SENTENCE = 5
WIDEN = 2
MAX_EVIDENCE_UNITS = 80


# ---------- a small DOM ----------

class _Node:
    def __init__(self, tag: str, attrs: dict, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    def classes(self) -> set:
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.walk()

    def text(self, skip=lambda node: False) -> str:
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif not skip(child):
                parts.append(child.text(skip))
        return "".join(parts)

    def ancestors(self):
        node = self
        while node is not None:
            yield node
            node = node.parent


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self.stack = [self.root]
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in _HIDDEN:
            self.hidden += 1
            return
        node = _Node(tag, {key: value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag not in _HIDDEN:
            self.stack[-1].children.append(_Node(tag, {key: value or "" for key, value in attrs}, self.stack[-1]))

    def handle_endtag(self, tag):
        if tag in _HIDDEN:
            self.hidden = max(0, self.hidden - 1)
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if not self.hidden:
            self.stack[-1].children.append(data)


def parse_html(html: str) -> _Node:
    tree = _Tree()
    tree.feed(html)
    tree.close()
    return tree.root


def _is_supplement(node: _Node) -> bool:
    return node.tag == "aside" and "supplement" in node.classes()


def _in(node: _Node, test) -> bool:
    return any(test(ancestor) for ancestor in node.ancestors())


def _seconds(label: str) -> int:
    total = 0
    for part in label.split(":"):
        total = total * 60 + int(part)
    return total


def _sections(root: _Node) -> list:
    """(section node, title, [(start s, end s), ...]) for every chapter with a section-time."""
    found = []
    for node in root.walk():
        if node.tag != "section":
            continue
        heading = next((child for child in node.walk() if child.tag == "h2"), None)
        if heading is None:
            continue
        title_node = next((child for child in heading.walk() if "section-title" in child.classes()), heading)
        time_node = next((child for child in heading.walk() if "section-time" in child.classes()), None)
        ranges = [(_seconds(a), _seconds(b)) for a, b in _RANGE.findall(time_node.text() if time_node else "")]
        found.append((node, title_node.text(lambda n: "section-time" in n.classes()).strip(), ranges))
    return found


def _section_of(node: _Node, sections: list):
    return next((entry for entry in sections if _in(node, lambda a, s=entry[0]: a is s)), None)


def _order(units: list) -> dict:
    return {unit["unit_id"]: index for index, unit in enumerate(units)}


def _cited(node: _Node, order: dict) -> list:
    """Unit indices cited by the nearest element (itself or an ancestor) with data-source-units."""
    for ancestor in node.ancestors():
        ids = (ancestor.attrs.get("data-source-units") or "").split()
        indices = [order[unit_id] for unit_id in ids if unit_id in order]
        if indices:
            return indices
    return []


def _range_units(ranges: list, units: list) -> list:
    picked = [unit["unit_id"] for unit in units
              if any(start * 1000 <= unit["start_ms"] < end * 1000 for start, end in ranges)]
    return picked[:MAX_EVIDENCE_UNITS]


# ---------- program metrics ----------

def component_counts(html: str) -> dict:
    counts = dict.fromkeys(COMPONENT_TAGS + COMPONENT_CLASSES, 0)
    for node in parse_html(html).walk():
        if node.tag in COMPONENT_TAGS:
            counts[node.tag] += 1
        for name in COMPONENT_CLASSES:
            if name in node.classes():
                counts[name] += 1
    counts["total"] = sum(counts.values())
    return counts


def citation_coverage(html: str, units: list) -> dict:
    """Each data-source-units attribute stands for the span from its first to its last unit."""
    order = _order(units)
    covered: set = set()
    for node in parse_html(html).walk():
        indices = [order[i] for i in (node.attrs.get("data-source-units") or "").split() if i in order]
        if indices:
            covered.update(range(min(indices), max(indices) + 1))
    longest, start = 0.0, None
    for index, unit in enumerate(units):
        if index in covered:
            start = None
            continue
        start = unit["start_ms"] if start is None else start
        longest = max(longest, (unit["end_ms"] - start) / 60000)
    total = len(units)
    return {"covered": len(covered), "total": total, "share": len(covered) / total if total else 0.0,
            "longest_gap_min": longest}


def _marks(html: str) -> set:
    return {token for node in parse_html(html).walk() for token in (node.attrs.get("data-points") or "").split()}


def time_coverage(html: str, units: list, ledger, skipped=frozenset()):
    """E14's 时间覆盖 for a report with a ledger: the share of the transcript's units under points the
    report marks, and the longest run of units under neither a written point nor a skip (the ledger's
    skipped stretches and the plan's skipped points are left out of both)."""
    if not ledger:
        return None
    order = _order(units)

    def span(entry: dict) -> range:
        first, last = (order.get(unit_id) for unit_id in entry.get("units") or [None, None])
        return range(first, last + 1) if first is not None and last is not None else range(0)

    marked = _marks(html)
    covered = {index for point in ledger["points"] if point["id"] in marked for index in span(point)}
    excluded = {index for point in ledger["points"] if point["id"] in skipped for index in span(point)}
    excluded |= {index for skip in ledger.get("skips") or [] for index in span(skip)}
    excluded -= covered
    counted = len(units) - len(excluded)
    longest, start = 0.0, None
    for index, unit in enumerate(units):
        if index in covered or index in excluded:
            start = None
            continue
        start = unit["start_ms"] if start is None else start
        longest = max(longest, (unit["end_ms"] - start) / 60000)
    return {"share": len(covered) / counted if counted else 0.0, "longest_gap_min": longest, "excluded": len(excluded)}


def points_coverage(html: str, points: list, skipped=frozenset()):
    """Share of the key points (not legally skipped) that some data-points attribute marks."""
    wanted = [point for point in points if point not in skipped]
    if not wanted:
        return None
    marked = {token for node in parse_html(html).walk() for token in (node.attrs.get("data-points") or "").split()}
    return sum(point in marked for point in wanted) / len(wanted)


def chapter_density(html: str) -> list:
    chapters = []
    for node, title, ranges in _sections(parse_html(html)):
        minutes = sum(end - start for start, end in ranges) / 60
        chars = len(_CJK.findall(node.text(lambda n: n.tag == "h2")))
        chapters.append({"title": title, "minutes": minutes, "chars": chars,
                         "per_minute": chars / minutes if minutes else None})
    return chapters


def cjk_counts(html: str, units: list) -> dict:
    root = parse_html(html)
    body = next((node for node in root.walk() if node.tag == "body"), root)
    return {"report": len(_CJK.findall(body.text())),
            "transcript": sum(len(_CJK.findall(unit.get("canonical_text") or "")) for unit in units)}


# ---------- faithfulness ----------

WINDOW, STRIDE, MATCHES = 12, 6, 2
_K1, _B = 1.5, 0.75
_DROP = re.compile(r"[^一-鿿A-Za-z0-9]")


def _grams(text: str) -> list:
    """Character bigrams of the wordy characters: no Chinese word segmenter needed."""
    clean = _DROP.sub("", text.lower())
    return [clean[i:i + 2] for i in range(len(clean) - 1)]


class _Passages:
    """BM25 over overlapping windows of transcript units: where a sentence's content really is,
    whatever its citation says."""

    def __init__(self, units: list):
        starts = range(0, max(len(units) - WINDOW, 0) + 1, STRIDE) if units else []
        self.windows = [(start, min(start + WINDOW, len(units))) for start in starts]
        if units and self.windows[-1][1] < len(units):
            self.windows.append((max(0, len(units) - WINDOW), len(units)))
        self.docs = [Counter(_grams("".join(u.get("canonical_text", "") for u in units[a:b])))
                     for a, b in self.windows]
        lengths = [sum(doc.values()) for doc in self.docs]
        self.lengths, self.average = lengths, (sum(lengths) / len(lengths)) if lengths else 1.0
        frequency = Counter(gram for doc in self.docs for gram in doc)
        total = len(self.docs)
        self.idf = {gram: math.log(1 + (total - n + 0.5) / (n + 0.5)) for gram, n in frequency.items()}

    def best(self, text: str, limit: int = MATCHES) -> list:
        terms = set(_grams(text))
        scored = []
        for index, doc in enumerate(self.docs):
            norm = _K1 * (1 - _B + _B * self.lengths[index] / (self.average or 1.0))
            score = sum(self.idf[t] * doc[t] * (_K1 + 1) / (doc[t] + norm) for t in terms if t in doc)
            if score > 0:
                scored.append((score, index))
        scored.sort(reverse=True)
        return [self.windows[index] for _score, index in scored[:limit]]


def _leaf_blocks(root: _Node):
    for node in root.walk():
        if node.tag in _BLOCKS and not any(child.tag in _BLOCKS for child in node.walk()):
            yield node


def report_sentences(html: str, units: list) -> list:
    """Body sentences with the transcript units that should support them: the nearest cited units
    widened by two on each side (else the units inside the chapter's section-time), plus the
    passages that best match the sentence anywhere in the transcript, since citations are often
    off. Supplements, figure captions and headings are left out."""
    root, order = parse_html(html), _order(units)
    sections = _sections(root)
    passages = _Passages(units)
    sentences = []
    for block in _leaf_blocks(root):
        if _in(block, _is_supplement) or _in(block, lambda a: a.tag in ("figure", "header", "h1", "h2")):
            continue
        cited = _cited(block, order)
        if cited:
            low, high = max(0, min(cited) - WIDEN), min(len(units) - 1, max(cited) + WIDEN)
            evidence = [units[i]["unit_id"] for i in range(low, high + 1)]
        else:
            section = _section_of(block, sections)
            evidence = _range_units(section[2], units) if section else []
        if not evidence:
            continue
        for piece in _SENTENCE_END.split(block.text()):
            text = " ".join(piece.split())
            if len(_WORDY.findall(text)) < MIN_SENTENCE:
                continue
            matched = {unit["unit_id"] for start, end in passages.best(text) for unit in units[start:end]}
            wanted = set(evidence) | matched
            sentences.append({"text": text, "units": [u["unit_id"] for u in units if u["unit_id"] in wanted]})
    return sentences


def sample_sentences(sentences: list, count: int, *, seed: int = 7) -> list:
    if len(sentences) <= count:
        return list(sentences)
    picked = sorted(random.Random(seed).sample(range(len(sentences)), count))
    return [sentences[index] for index in picked]


def report_supplements(html: str, units: list) -> list:
    root = parse_html(html)
    sections = _sections(root)
    found = []
    for node in root.walk():
        if not _is_supplement(node):
            continue
        text = " ".join(node.text(lambda n: "supplement-label" in n.classes()).split())
        section = _section_of(node, sections)
        found.append({"text": text, "units": _range_units(section[2], units) if section else []})
    return found


# ---------- prompts and replies ----------

def _clock(ms: int) -> str:
    seconds = int(ms // 1000)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def question_prompt(block: list) -> str:
    lines = "\n".join(f"[{unit['unit_id']} {_clock(unit['start_ms'])}] {unit.get('canonical_text', '')}"
                      for unit in block)
    return (
        f"下面是一段视频转写，每行开头是单元编号和时间。请只根据这段转写，出 {QUESTIONS_PER_BLOCK} 道题，"
        "用来检验读者有没有掌握这段内容：\n"
        "- 覆盖这段里最重要的实质内容：定义、论断和理由、例子、数字、人名书名、步骤、条件、经历；\n"
        "- 不出关于口头禅、寒暄、广告、课堂管理的题；\n"
        "- 每题有明确的标准答案（一两句话），答案必须能在这段转写里找到；题目本身不泄露答案；\n"
        "- units 写出答案所在的单元编号。\n"
        '只输出 JSON：{"questions": [{"q": "题目", "answer": "标准答案", "units": ["unit-000123"]}]}\n\n'
        f"转写：\n{lines}\n"
    )


def parse_questions(text: str, block_ids: list) -> tuple:
    value = first_json_object(text or "")
    if not isinstance(value, dict):
        return [], ["回复不是合法 JSON"]
    allowed, kept, problems = set(block_ids), [], []
    for index, item in enumerate(value.get("questions") or [], 1):
        item = item if isinstance(item, dict) else {}
        question, answer = str(item.get("q") or "").strip(), str(item.get("answer") or "").strip()
        units = [unit for unit in item.get("units") or [] if isinstance(unit, str)]
        if not question or not answer:
            problems.append(f"第 {index} 题缺题目或答案")
        elif not units or not set(units) <= allowed:
            problems.append(f"第 {index} 题的单元不在这一块里")
        elif len(kept) < QUESTIONS_PER_BLOCK:
            kept.append({"q": question, "answer": answer, "units": units})
    return kept, problems


def answer_prompt(report_markdown: str, questions: list) -> str:
    numbered = "\n".join(f"{index}. {question['q']}" for index, question in enumerate(questions, 1))
    return (
        "下面是一份视频精读报告。请只根据报告里写了的内容回答问题，不用你自己的知识；"
        "报告里找不到答案的，回答「未提及」。\n"
        '只输出 JSON：{"answers": {"1": "答案", "2": "未提及"}}\n\n'
        f"报告：\n{report_markdown}\n\n问题：\n{numbered}\n"
    )


def _numbered(text: str, key: str, count: int) -> list:
    value = first_json_object(text or "")
    found = value.get(key) if isinstance(value, dict) else None
    found = found if isinstance(found, dict) else {}
    return [found.get(str(index)) for index in range(1, count + 1)]


def parse_answers(text: str, count: int) -> list:
    return [str(answer or "").strip() or "未提及" for answer in _numbered(text, "answers", count)]


def grade_prompt(rows: list) -> str:
    numbered = "\n".join(
        f"{index}. 题目：{row['q']}\n   标准答案：{row['answer']}\n   报告作答：{row['reply']}"
        for index, row in enumerate(rows, 1))
    return (
        "逐题比较「报告作答」和「标准答案」，给出一个判定：\n"
        "- 正确：要点都答对了；\n- 部分正确：只答对一部分，或不够具体；\n"
        "- 未提及：作答是「未提及」，或者没有答到点上；\n- 错误：与标准答案矛盾。\n"
        '只输出 JSON：{"grades": {"1": "正确"}}\n\n' + numbered + "\n"
    )


def parse_grades(text: str, count: int) -> list:
    return [grade if grade in GRADES else None for grade in _numbered(text, "grades", count)]


def qa_score(grades: list) -> dict:
    total = len(grades)
    tally = {name: sum(grade == label for grade in grades)
             for name, label in (("correct", "正确"), ("partial", "部分正确"), ("missing", "未提及"), ("wrong", "错误"))}
    tally["ungraded"] = sum(grade is None for grade in grades)
    return {"total": total, **tally, "score": (tally["correct"] + 0.5 * tally["partial"]) / total if total else 0.0}


def _evidence(unit_ids: list, texts: dict) -> str:
    return "".join(texts.get(unit_id, "") for unit_id in unit_ids)


def faithfulness_prompt(items: list, texts: dict) -> str:
    numbered = "\n".join(f"{index}. 句子：{item['text']}\n   原文：{_evidence(item['units'], texts)}"
                         for index, item in enumerate(items, 1))
    return (
        "下面每一条是精读报告里的一句话，后面附着它依据的视频原文。判断这句话能不能由原文支持：\n"
        "- 有依据：原文说了这个意思；\n- 部分有依据：有一部分原文没有说，或者比原文说得更具体；\n"
        "- 无依据：原文没有这个意思，或者与原文矛盾。\n"
        '只输出 JSON：{"verdicts": {"1": "有依据"}}\n\n' + numbered + "\n"
    )


def contradiction_prompt(items: list, texts: dict) -> str:
    numbered = "\n".join(f"{index}. 补充说明：{item['text']}\n   这一章的原文：{_evidence(item['units'], texts)}"
                         for index, item in enumerate(items, 1))
    return (
        "下面每一条「补充说明」是报告作者用自己的知识补充的背景，不要求原文里有。"
        "只判断它和这一章的原文有没有矛盾：矛盾 / 不矛盾。\n"
        '只输出 JSON：{"verdicts": {"1": "不矛盾"}}\n\n' + numbered + "\n"
    )


def parse_verdicts(text: str, count: int, allowed: tuple) -> list:
    return [verdict if verdict in allowed else None for verdict in _numbered(text, "verdicts", count)]


# ---------- cost ----------

def estimate_tokens(text: str) -> int:
    """A rough count: one token per CJK character, one per four other characters."""
    cjk = len(_CJK.findall(text or ""))
    return cjk + (len(text or "") - cjk + 3) // 4


def estimate_cost(calls: list) -> dict:
    tokens_in = sum(estimate_tokens(call["in"]) for call in calls)
    tokens_out = sum(estimate_tokens(call["out"]) for call in calls)
    return {"calls": len(calls), "tokens_in": tokens_in, "tokens_out": tokens_out,
            "usd": tokens_in * PRICE_IN / 1_000_000 + tokens_out * PRICE_OUT / 1_000_000}


# ---------- the whole evaluation ----------

def _batches(items: list, size: int) -> list:
    return [items[start:start + size] for start in range(0, len(items), size)]


def ensure_questions(units: list, questions_file: Path, call, workers: int = 3) -> dict:
    """The item's kept questions, made (once) from its transcript blocks."""
    if questions_file.is_file():
        return json.loads(questions_file.read_text(encoding="utf-8"))

    def one_block(block):
        ids = [unit["unit_id"] for unit in block]
        kept, problems = parse_questions(call(question_prompt(block)), ids)
        if not kept:  # one more try for a block that gave nothing usable
            kept, more = parse_questions(call(question_prompt(block)), ids)
            problems += more
        return kept, problems

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one_block, chunk_units(units, seconds=300)))
    saved = {"questions": [q for kept, _ in results for q in kept],
             "problems": [p for _, problems in results for p in problems]}
    questions_file.parent.mkdir(parents=True, exist_ok=True)
    questions_file.write_bytes(json.dumps(saved, ensure_ascii=False, indent=2).encode("utf-8"))
    return saved


def evaluate_report(units: list, html: str, questions_file, ask, *, points=None, skipped=frozenset(),
                    ledger=None, seed: int = 7, workers: int = 3) -> dict:
    calls: list = []

    def call(prompt: str) -> str:
        reply = ask(prompt) or ""
        calls.append({"in": prompt, "out": reply})
        return reply

    texts = {unit["unit_id"]: unit.get("canonical_text", "") for unit in units}
    questions = ensure_questions(units, Path(questions_file), call, workers)["questions"]
    markdown = report_to_markdown(html)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        answer_batches = list(pool.map(
            lambda batch: parse_answers(call(answer_prompt(markdown, batch)), len(batch)), _batches(questions, 20)))
        answers = [answer for batch in answer_batches for answer in batch]
        rows = [{**question, "reply": answer} for question, answer in zip(questions, answers, strict=True)]
        grade_batches = list(pool.map(
            lambda batch: parse_grades(call(grade_prompt(batch)), len(batch)), _batches(rows, 20)))
        grades = [grade for batch in grade_batches for grade in batch]
        sampled = sample_sentences(report_sentences(html, units), 40, seed=seed)
        faithful = [v for batch in pool.map(
            lambda batch: parse_verdicts(call(faithfulness_prompt(batch, texts)), len(batch), FAITHFUL),
            _batches(sampled, 10)) for v in batch]
        supplements = report_supplements(html, units)[:20]
        checked = [v for batch in pool.map(
            lambda batch: parse_verdicts(call(contradiction_prompt(batch, texts)), len(batch), CONTRADICTION),
            _batches(supplements, 10)) for v in batch]
    return {
        "qa": qa_score(grades),
        "qa_details": [{**row, "grade": grade} for row, grade in zip(rows, grades, strict=True)],
        "faithfulness": {"sampled": len(sampled), **{name: faithful.count(name) for name in FAITHFUL},
                         "ungraded": faithful.count(None)},
        "faithfulness_details": [{**item, "verdict": verdict} for item, verdict in zip(sampled, faithful, strict=True)],
        "supplements": {"checked": len(supplements), **{name: checked.count(name) for name in CONTRADICTION},
                        "ungraded": checked.count(None)},
        "points_coverage": points_coverage(html, points or [], skipped),
        "time": time_coverage(html, units, ledger, skipped),
        "skipped": len(skipped),
        "citation": citation_coverage(html, units),
        "chapters": chapter_density(html),
        "components": component_counts(html),
        "cjk": cjk_counts(html, units),
        "cost": estimate_cost(calls),
    }
