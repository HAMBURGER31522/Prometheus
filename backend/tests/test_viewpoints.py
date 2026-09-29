"""「编者观点（非视频内容）」 (PLAN 15.4.11a-4): the editor's view may disagree with the video, but
every link it gives as evidence is opened; dead or unrelated links go, and a point left without a
source says so and drops a level of confidence."""

from prometheus.report import viewpoints

PAGES = {
    "https://en.wikipedia.org/wiki/Coffee_extraction": "Coffee extraction - Wikipedia. Extraction yield and brew strength.",
    "https://example.org/unrelated": "Garden tools and lawn care for beginners.",
}


def fetch(url: str) -> str:
    if url not in PAGES:
        raise OSError("404")
    return PAGES[url]


FRAGMENT = """<section><h2>水温</h2><p data-points="K001">正文。</p>
<aside class="viewpoint"><p class="viewpoint-label">编者观点（非视频内容）</p><ul>
<li>萃取率的说法偏保守。<span class="confidence">置信度：高</span>
依据：<a href="https://en.wikipedia.org/wiki/Coffee_extraction">Coffee extraction (Wikipedia)</a>、<a href="https://example.org/gone">Old coffee blog</a></li>
<li>浅烘豆不一定要高水温。<span class="confidence">置信度：高</span>
依据：<a href="https://example.org/unrelated">Coffee roasting guide</a></li>
</ul></aside></section>"""


def test_a_working_related_link_stays_and_a_dead_one_goes():
    fixed, stats = viewpoints.verify(FRAGMENT, fetch)
    assert 'href="https://en.wikipedia.org/wiki/Coffee_extraction"' in fixed
    assert "https://example.org/gone" not in fixed
    assert stats == {"points": 2, "links": 3, "kept": 1, "dropped": 2, "unsourced": 1}


def test_a_point_left_without_a_source_says_so_and_drops_a_level():
    fixed, _stats = viewpoints.verify(FRAGMENT, fetch)
    second = fixed.split("<li>")[2]
    assert "https://example.org/unrelated" not in second  # it opened, but it is about something else
    assert "没有可核实的来源" in second and "置信度：中" in second
    first = fixed.split("<li>")[1]
    assert "置信度：高" in first and "没有可核实的来源" not in first


def test_confidence_bottoms_out_at_low_and_other_markup_is_untouched():
    low = FRAGMENT.replace("置信度：高", "置信度：低")
    fixed, _stats = viewpoints.verify(low, fetch)
    assert "置信度：低" in fixed.split("<li>")[2]
    plain = '<section><p>没有编者观点。<a href="https://example.org/gone">链接</a></p></section>'
    assert viewpoints.verify(plain, fetch) == (plain, {"points": 0, "links": 0, "kept": 0, "dropped": 0,
                                                       "unsourced": 0})
