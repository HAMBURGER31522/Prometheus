"""「编者观点（非视频内容）」 (PLAN 15.4.11a-4, user 2026-09-29).

Where the video is contested, the editor gives its own view with a confidence and sources. The
writer cannot browse, so a link it gives comes from memory: every one is opened, and kept only when
the page answers and is about what the link says (shared words between the point, the link's name
and the page). A point left without a source says so and drops a level of confidence.
"""

import html as html_lib
import re
import urllib.request

LEVELS = ("高", "中", "低")
UNSOURCED = "（没有可核实的来源）"
USER_AGENT = "Mozilla/5.0 (Prometheus link check)"
MIN_SHARED = 2
_ASIDE = re.compile(r'<aside class="viewpoint">.*?</aside>', re.DOTALL)
_ITEM = re.compile(r"<li\b[^>]*>.*?</li>", re.DOTALL)
_LINK = re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_CONFIDENCE = re.compile(r"置信度：(高|中|低)")
_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_CJK = re.compile(r"[一-鿿]+")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def open_page(url: str, *, proxy: str = "") -> str:
    """The page's title and text (the first 200 KB); raises when it does not open."""
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy.strip() else []
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.build_opener(*handlers).open(request, timeout=10) as response:
        body = response.read(200_000).decode("utf-8", "replace")
    title = _TITLE.search(body)
    return (title.group(1) if title else "") + " " + _TAG.sub(" ", body)


def _tokens(text: str) -> set:
    plain = html_lib.unescape(_TAG.sub(" ", text or "")).lower()
    words = set(_WORD.findall(plain))
    bigrams = {run[i:i + 2] for run in _CJK.findall(plain) for i in range(len(run) - 1)}
    return words | bigrams


def _related(point: str, name: str, page: str) -> bool:
    return len(_tokens(point + " " + name) & _tokens(page)) >= MIN_SHARED


def _check_item(item: str, fetch, stats: dict) -> str:
    links = _LINK.findall(item)
    stats["points"] += 1
    stats["links"] += len(links)
    point = _LINK.sub(" ", item)
    kept = 0
    for url, name in links:
        try:
            page = fetch(url)
        except Exception:  # noqa: BLE001 - whatever keeps a page from opening, the link goes
            page = None
        if page is not None and _related(point, name, page):
            kept += 1
        else:
            item = item.replace(f'href="{url}"', "\0", 1)
            item = re.sub(r'<a\b[^>]*\0[^>]*>.*?</a>[、，,]?', "", item, count=1, flags=re.DOTALL)
    stats["kept"] += kept
    stats["dropped"] += len(links) - kept
    if links and not kept:
        stats["unsourced"] += 1
        item = _CONFIDENCE.sub(lambda m: "置信度：" + LEVELS[min(LEVELS.index(m.group(1)) + 1, len(LEVELS) - 1)], item)
        item = item.replace("</li>", UNSOURCED + "</li>")
    return item


def verify(fragment: str, fetch) -> tuple:
    """(fragment with only verified links, {points, links, kept, dropped, unsourced})."""
    stats = {"points": 0, "links": 0, "kept": 0, "dropped": 0, "unsourced": 0}

    def fix_box(match: re.Match) -> str:
        return _ITEM.sub(lambda item: _check_item(item.group(0), fetch, stats), match.group(0))

    return _ASIDE.sub(fix_box, fragment), stats
