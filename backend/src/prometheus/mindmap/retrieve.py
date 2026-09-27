"""Evidence for mind map leaves (PLAN 15.4.9, D-40).

A leaf's evidence is the chapter its time falls in (its full text, not the outline's
excerpt) plus the report passages that best match its label and summary elsewhere in the
report (BM25 over character bigrams, which needs no Chinese word segmenter).
"""

import html as html_lib
import math
import re
import unicodedata
from collections import Counter

from prometheus.report.outline import SECTION_TIME_RE

MAX_SECTION = 1500   # characters of the leaf's own chapter
MAX_PASSAGE = 300    # characters per related passage
RELATED = 2          # related passages from other chapters
MAX_EVIDENCE = 2400
TIME_SLACK_S = 5

_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
_BLOCK = re.compile(r"<(p|li|td|th|blockquote|figcaption|h3|h4)\b[^>]*>(.*?)</\1>", re.DOTALL)
_SKIP = re.compile(r"<(style|script|svg)\b[^>]*>.*?</\1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(_TAG.sub(" ", fragment))).strip()


def _seconds(label: str) -> int:
    parts = [int(part) for part in label.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _chapters(html: str) -> list:
    """(heading text, body html) per <h2>."""
    heads = list(_H2.finditer(html))
    return [
        (_clean(match.group(1)), html[match.end():heads[i + 1].start() if i + 1 < len(heads) else len(html)])
        for i, match in enumerate(heads)
    ]


def passages(html: str) -> list:
    """Every text block of every chapter: [{"section": index, "text": str}]."""
    out = []
    for index, (_heading, body) in enumerate(_chapters(html)):
        seen = set()
        for _tag, inner in _BLOCK.findall(_SKIP.sub(" ", body)):
            text = _clean(inner)
            if len(text) >= 8 and text not in seen:
                seen.add(text)
                out.append({"section": index, "text": text})
    return out


def section_text(html: str, index: int) -> str:
    return " ".join(p["text"] for p in passages(html) if p["section"] == index)


def _grams(text: str) -> list:
    chars = [c.lower() for c in text if unicodedata.category(c)[0] in "LN"]
    return ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]


class Index:
    """BM25 over the report's passages, plus the chapter time ranges."""

    K1, B = 1.5, 0.75

    def __init__(self, html: str):
        self.passages = passages(html)
        self.ranges = []
        for heading, _body in _chapters(html):
            match = SECTION_TIME_RE.search(heading)
            self.ranges.append((_seconds(match.group(1)), _seconds(match.group(2))) if match else None)
        self.docs = [Counter(_grams(p["text"])) for p in self.passages]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.average = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        frequency = Counter(gram for doc in self.docs for gram in doc)
        total = len(self.docs)
        self.idf = {gram: math.log(1 + (total - n + 0.5) / (n + 0.5)) for gram, n in frequency.items()}

    def section_for(self, seconds) -> int | None:
        if seconds is None:
            return None
        before = None
        for index, span in enumerate(self.ranges):
            if span is None:
                continue
            start, end = span
            if start - TIME_SLACK_S <= seconds <= end + TIME_SLACK_S:
                return index
            if start <= seconds:
                before = index
        return before

    def search(self, query: str, *, exclude: int | None = None, limit: int = RELATED) -> list:
        terms = set(_grams(query))
        scored = []
        for index, doc in enumerate(self.docs):
            if self.passages[index]["section"] == exclude:
                continue
            norm = self.K1 * (1 - self.B + self.B * self.lengths[index] / self.average)
            score = sum(self.idf.get(t, 0) * doc[t] * (self.K1 + 1) / (doc[t] + norm) for t in terms if t in doc)
            if score > 0:
                scored.append((score, index))
        scored.sort(reverse=True)
        return [self.passages[index] for _score, index in scored[:limit]]

    def evidence(self, leaf: dict) -> str:
        parts = []
        section = self.section_for(leaf.get("time"))
        if section is not None:
            chapter = " ".join(p["text"] for p in self.passages if p["section"] == section)
            parts.append(chapter[:MAX_SECTION])
        query = f"{leaf.get('label', '')} {leaf.get('summary', '')}"
        for passage in self.search(query, exclude=section):
            parts.append(passage["text"][:MAX_PASSAGE])
        return "\n".join(part for part in parts if part)[:MAX_EVIDENCE]
