"""精读.md: the report as Markdown for AI readers (PLAN 15.4.1).

The HTML stays the human copy; this is the plain channel an AI (or Obsidian)
reads: headings with their section times, paragraphs, lists, tables and figure
captions. Styles, scripts, charts, navigation and inline images are dropped.
"""

import re
from html.parser import HTMLParser

_SKIP = {"style", "script", "svg", "nav", "footer", "head", "template", "noscript", "button"}
_BLOCKS = {"p", "div", "section", "article", "header", "main", "aside", "figure",
           "details", "summary", "dl", "dt", "dd"}
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _Converter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.inline: list[str] = []
        self.skip_depth = 0
        self.lists: list[list] = []          # [kind, counter]
        self.quote = 0
        self.heading = 0
        self.href: list[str | None] = []
        self.table: list[list[str]] | None = None
        self.cell: list[str] | None = None
        self.spans: list[bool] = []         # True for a section-time span

    # -- helpers ---------------------------------------------------------
    def _text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.inline)).strip()

    def _flush(self, prefix: str = "") -> None:
        text = self._text()
        self.inline = []
        if not text:
            return
        if self.quote:
            prefix = "> " + prefix
        self.lines.append(prefix + text)
        if not self.lists:
            self.lines.append("")

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.skip_depth or tag in _SKIP or "hidden" in attrs or attrs.get("aria-hidden") == "true":
            if tag not in ("br", "img", "meta", "link", "input", "hr"):
                self.skip_depth += 1
            return
        if tag in _HEADINGS:
            self._flush()
            self.heading = _HEADINGS[tag]
        elif tag in ("ul", "ol"):
            self._flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self._flush()
        elif tag == "blockquote":
            self._flush()
            self.quote += 1
        elif tag == "table":
            self._flush()
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.table.append([])
        elif tag in ("td", "th") and self.table is not None:
            self.cell = []
        elif tag == "br":
            self.inline.append(" ")
        elif tag in ("strong", "b"):
            self.inline.append("**")
        elif tag in ("em", "i"):
            self.inline.append("*")
        elif tag == "a":
            href = attrs.get("href") or ""
            keep = href.startswith(("http://", "https://"))
            self.href.append(href if keep else None)
            if keep:
                self.inline.append("[")
        elif tag == "figcaption":
            self._flush()
            self.inline.append("*图：")
        elif tag == "span":
            is_time = "section-time" in (attrs.get("class") or "")
            self.spans.append(is_time)
            if is_time:
                self.inline.append("（")
        elif tag in _BLOCKS:
            self._flush()

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag not in ("br", "img", "meta", "link", "input", "hr"):
                self.skip_depth -= 1
            return
        if tag in _HEADINGS and self.heading:
            self._flush("#" * self.heading + " ")
            self.heading = 0
        elif tag in ("ul", "ol") and self.lists:
            self._flush()
            self.lists.pop()
            if not self.lists:
                self.lines.append("")
        elif tag == "li" and self.lists:
            kind = self.lists[-1]
            kind[1] += 1
            marker = f"{kind[1]}. " if kind[0] == "ol" else "- "
            self._flush("  " * (len(self.lists) - 1) + marker)
        elif tag == "blockquote":
            self._flush()
            self.quote = max(0, self.quote - 1)
        elif tag in ("td", "th") and self.cell is not None and self.table:
            text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            self.table[-1].append(text)
            self.cell = None
        elif tag == "table" and self.table is not None:
            rows = [row for row in self.table if row]
            if rows:
                width = max(len(row) for row in rows)
                rows = [row + [""] * (width - len(row)) for row in rows]
                self.lines.append("| " + " | ".join(rows[0]) + " |")
                self.lines.append("| " + " | ".join(["---"] * width) + " |")
                self.lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                self.lines.append("")
            self.table = None
        elif tag in ("strong", "b"):
            self.inline.append("**")
        elif tag in ("em", "i"):
            self.inline.append("*")
        elif tag == "a" and self.href:
            href = self.href.pop()
            if href:
                self.inline.append(f"]({href})")
        elif tag == "figcaption":
            self.inline.append("*")
            self._flush()
        elif tag == "span" and self.spans:
            if self.spans.pop():
                self.inline.append("）")
            elif self.heading:
                self.inline.append(" ")   # the section-number badge before a title
        elif tag in _BLOCKS:
            self._flush()

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.cell is not None:
            self.cell.append(data)
        else:
            self.inline.append(data)


def report_to_markdown(html: str) -> str:
    converter = _Converter()
    converter.feed(html)
    converter.close()
    converter._flush()
    text = "\n".join(converter.lines)
    text = re.sub(r"\*\*\s*\*\*", "", text)          # empty emphasis left by styling spans
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"
